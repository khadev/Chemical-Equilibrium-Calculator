"""
ui/main_window.py
====================
Main application window — the View/Controller that wires together
InputPanel, ResultsPanel, WelcomePanel, session management, and the
CEAWorker background-thread execution pipeline.

Threading contract: CEAWorker runs on a daemon thread and reports
through a queue.Queue. This window polls that queue via
``self.after()`` — it never touches widgets from the worker thread.
"""
from __future__ import annotations

import copy
import csv
import logging
import os
from tkinter import Menu, TclError, filedialog, messagebox
from typing import Dict, List, Optional

import customtkinter as ctk

from core.cea_executor import CEAExecutor
from core.cea_worker import CEAWorker
from core.inp_builder import INPBuilder
from core.theme_manager import ThemeManager
from core.validator import PreFlightValidator
from models.cea_result import CEAResult
from models.formulation import Formulation
from models.species_database import SpeciesDatabase
from tools.settings_manager import SettingsManager
from ui.dialogs.nozzle_dialog import NozzleDesignerDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.input_panel import InputPanel
from ui.results_panel import ResultsPanel
from ui.welcome_panel import WelcomePanel

log = logging.getLogger(__name__)

_PALETTE = ["#3F51B5", "#00ACC1", "#43A047", "#FB8C00",
            "#E53935", "#8E24AA", "#00897B", "#F4511E"]


class Session:
    """A single formulation + its result, tracked in the sidebar."""

    _counter = 0

    def __init__(self, name: str = "") -> None:
        Session._counter += 1
        self.id = Session._counter
        self.name = name or f"Formulation {Session._counter}"
        self.formulation = Formulation(name=self.name)
        self.result: Optional[CEAResult] = None
        self.status = "pending"
        self.color = _PALETTE[(Session._counter - 1) % len(_PALETTE)]

    def has_result(self) -> bool:
        return self.result is not None and self.result.success


class MainWindow(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        # No withdraw(), no separate splash Toplevel, no deiconify() dance.
        #
        # Two earlier attempts to show a branded splash screen while
        # loading (first via a throwaway second root, then via a
        # withdrawn-root + Toplevel + deiconify handoff) both produced a
        # silent failure on Windows: the process runs cleanly to
        # mainloop() with zero exceptions, but the window never becomes
        # visible. That failure mode can't be reproduced in a Linux/Xvfb
        # sandbox (there's no real window manager to "lose track" of
        # anything), so it couldn't be validated there either time.
        #
        # Loading itself (species DB parse + widget construction) takes
        # about 3 seconds per the reported logs — there's no real
        # justification for a splash screen's added platform-interaction
        # risk. Building the window directly, visible from the very
        # first frame, is the simplest and most-tested Tkinter pattern
        # there is: every plain Tkinter/customtkinter tutorial does
        # exactly this, with no withdraw/deiconify/overrideredirect
        # involved at all.
        self._settings = SettingsManager()
        self._db = SpeciesDatabase()

        self._executor = CEAExecutor(
            fcea2_exe=self._settings.fcea2_exe(),
            work_dir=self._settings.cea_folder())
        self._validator = PreFlightValidator()

        self._sessions: List[Session] = []
        self._active: Optional[Session] = None
        self._active_worker: Optional[CEAWorker] = None
        self._engine_mode = "auto"

        self._setup_window()
        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._add_session()

        ThemeManager().apply(self)

        # Force the window to the front exactly once, defensively, in
        # case it was launched from a console that's holding focus —
        # this does NOT depend on any prior withdraw/deiconify state.
        self.lift()
        self.after(50, self.focus_force)

        # Log exactly what Tk thinks the window's geometry/state is.
        # If a visibility problem is ever reported again, this line
        # tells us immediately whether it's an off-screen-position
        # issue, a zero-size issue, or something else — rather than
        # guessing blind.
        self.update_idletasks()
        log.info(
            "MainWindow ready. DB: %d ox, %d fuels. "
            "geometry=%s state=%s viewable=%s screen=%dx%d",
            len(self._db.all_oxidizers()), len(self._db.all_fuels()),
            self.geometry(), self.state(), self.winfo_viewable(),
            self.winfo_screenwidth(), self.winfo_screenheight())

    # ── Window setup ──────────────────────────────────────────────────
    def _setup_window(self) -> None:
        version = self._settings.get("app", "version") or "1.0.0"
        self.title(f"CEA Calculator Pro  v{version}")
        width = self._settings.get("window", "width") or 1400
        height = self._settings.get("window", "height") or 900
        # Guard against a degenerate saved size (e.g. from a prior abnormal
        # exit while the window was still withdrawn, which can report
        # width/height of 1px) — never start smaller than the usable minimum.
        width = max(int(width), 1100)
        height = max(int(height), 680)
        # Always pin an explicit, guaranteed-on-screen position rather
        # than relying on the window manager's default placement, which
        # varies by platform/multi-monitor setup and was a candidate
        # explanation for a window appearing fully off-screen.
        self.geometry(f"{width}x{height}+50+50")
        self.minsize(1100, 680)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Menu bar (tkinter Menu, as specified) ────────────────────────
    def _build_menu(self) -> None:
        tr = self._settings.tr
        menubar = Menu(self)
        self.configure(menu=menubar)

        file_menu = Menu(menubar, tearoff=False)
        file_menu.add_command(label=tr("load_inp"), command=self._load_inp,
                              accelerator="Ctrl+O")
        file_menu.add_command(label=tr("save_inp"), command=self._save_inp,
                              accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label=tr("export_csv"), command=self._export_csv,
                              accelerator="Ctrl+E")
        file_menu.add_command(label="📊  Export Plots & Results to Excel…",
                              command=self._export_excel, accelerator="Ctrl+Shift+E")
        file_menu.add_command(label="📑  Export Research-Grade Report (.xlsx)…",
                              command=self._export_research_report, accelerator="Ctrl+Shift+R")
        file_menu.add_separator()
        file_menu.add_command(label=tr("exit"), command=self._on_close)
        menubar.add_cascade(label=tr("file"), menu=file_menu)

        analysis_menu = Menu(menubar, tearoff=False)
        analysis_menu.add_command(label="▶  " + tr("calculate"),
                                  command=self._on_calculate, accelerator="Ctrl+R")
        analysis_menu.add_command(label="✓  " + tr("validate"),
                                  command=self._on_validate, accelerator="Ctrl+Shift+V")
        analysis_menu.add_separator()
        analysis_menu.add_command(label=tr("run_all"), command=self._run_all)
        menubar.add_cascade(label=tr("analysis"), menu=analysis_menu)

        tools_menu = Menu(menubar, tearoff=False)
        tools_menu.add_command(label="🚀 " + tr("nozzle_designer"),
                               command=self._open_nozzle)
        tools_menu.add_command(label="↕  Unit Converter",
                               command=self._open_unit_converter)
        tools_menu.add_command(label="📥  Import Database (thermo.lib / trans.lib)…",
                               command=self._open_import_database)
        tools_menu.add_separator()
        from core.analysis_tools import tools_by_category
        for category, specs in tools_by_category().items():
            category_menu = Menu(tools_menu, tearoff=False)
            for spec in specs:
                category_menu.add_command(
                    label=spec.name,
                    command=lambda k=spec.key: self._open_tool(k))
            tools_menu.add_cascade(label=category, menu=category_menu)
        menubar.add_cascade(label=tr("tools"), menu=tools_menu)

        session_menu = Menu(menubar, tearoff=False)
        session_menu.add_command(label=tr("add_session"), command=self._add_session,
                                 accelerator="Ctrl+T")
        session_menu.add_command(label=tr("duplicate"), command=self._dup_session)
        menubar.add_cascade(label=tr("session"), menu=session_menu)

        # Settings — top-level menu, as required
        settings_menu = Menu(menubar, tearoff=False)
        settings_menu.add_command(label="⚙  Open Settings…",
                                  command=self._open_settings, accelerator="Ctrl+,")
        settings_menu.add_separator()
        settings_menu.add_command(label="Language: English",
                                  command=lambda: self._set_language("en"))
        settings_menu.add_command(label="Language: Français",
                                  command=lambda: self._set_language("fr"))
        menubar.add_cascade(label=tr("settings"), menu=settings_menu)

        help_menu = Menu(menubar, tearoff=False)
        help_menu.add_command(label=tr("about"), command=self._show_about)
        menubar.add_cascade(label=tr("help"), menu=help_menu)

        self.bind("<Control-r>", lambda e: self._on_calculate())
        self.bind("<Control-o>", lambda e: self._load_inp())
        self.bind("<Control-s>", lambda e: self._save_inp())
        self.bind("<Control-e>", lambda e: self._export_csv())
        self.bind("<Control-E>", lambda e: self._export_excel())
        self.bind("<Control-R>", lambda e: self._export_research_report())
        self.bind("<Control-t>", lambda e: self._add_session())
        self.bind("<Control-comma>", lambda e: self._open_settings())

    # ── Toolbar ───────────────────────────────────────────────────────
    def _build_toolbar(self) -> None:
        colors = ThemeManager().get_colors()
        bar = ctk.CTkFrame(self, height=46, fg_color=colors["sidebar"],
                          corner_radius=0)
        bar.pack(fill="x", side="top")

        self._run_btn = ctk.CTkButton(
            bar, text="▶  Calculate", height=32, command=self._on_calculate)
        self._run_btn.pack(side="left", padx=(8, 4), pady=7)

        ctk.CTkButton(
            bar, text="✓  Validate", height=32,
            fg_color=colors["surface"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._on_validate
        ).pack(side="left", padx=4, pady=7)

        ctk.CTkButton(
            bar, text="🚀 Nozzle", height=32,
            fg_color=colors["surface"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._open_nozzle
        ).pack(side="left", padx=4, pady=7)

        ctk.CTkButton(
            bar, text="⚙ Settings", height=32,
            fg_color=colors["surface"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._open_settings
        ).pack(side="left", padx=4, pady=7)

        ctk.CTkButton(
            bar, text="📥 Import DB", height=32,
            fg_color=colors["surface"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._open_import_database
        ).pack(side="left", padx=4, pady=7)

        ctk.CTkButton(
            bar, text="📊 Export Excel", height=32,
            fg_color=colors["surface"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._export_excel
        ).pack(side="left", padx=4, pady=7)

        ctk.CTkButton(
            bar, text="📑 Research Report", height=32,
            fg_color=colors["surface"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._export_research_report
        ).pack(side="left", padx=4, pady=7)

        sep = ctk.CTkFrame(bar, width=1, height=28, fg_color=colors["border"])
        sep.pack(side="left", padx=8, pady=7)

        ctk.CTkLabel(bar, text="Engine:", font=ctk.CTkFont(size=11),
                    text_color=colors["text_secondary"]).pack(side="left", padx=(0, 4))
        self._engine_mode_var = ctk.StringVar(value="Auto")
        engine_switch = ctk.CTkSegmentedButton(
            bar, values=["Auto", "CEA Python", "FCEA2 Only"],
            variable=self._engine_mode_var, height=28,
            command=self._on_engine_mode_changed)
        engine_switch.pack(side="left", padx=(0, 4), pady=7)

        self._cea_status_label = ctk.CTkLabel(
            bar, text="", font=ctk.CTkFont(size=11, weight="bold"))
        self._cea_status_label.pack(side="right", padx=10)
        self._refresh_cea_status()

    # ── Body: sidebar + input panel + results panel ────────────────────
    def _build_body(self) -> None:
        colors = ThemeManager().get_colors()
        container = ctk.CTkFrame(self, fg_color=colors["bg"], corner_radius=0)
        container.pack(fill="both", expand=True)

        self._sidebar = self._build_sidebar(container)
        self._sidebar.pack(side="left", fill="y")

        self._input_panel = InputPanel(container)
        self._input_panel.configure(width=320)
        self._input_panel.pack(side="left", fill="y", padx=(2, 2))
        self._input_panel.on_calculate = self._on_calculate_from_panel
        self._input_panel.on_validate = self._on_validate_from_panel
        self._input_panel.on_save_inp = self._on_save_inp_request
        self._input_panel.on_load_inp = self._load_inp
        self._input_panel.on_clear = self._on_clear_active

        right = ctk.CTkFrame(container, fg_color=colors["bg"], corner_radius=0)
        right.pack(side="left", fill="both", expand=True)

        self._welcome_panel = WelcomePanel(right)
        self._welcome_panel.pack(fill="both", expand=True)
        self._welcome_panel.on_preset_selected = self._load_preset

        self._results_panel = ResultsPanel(right)
        self._right_container = right

    def _build_sidebar(self, parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
        colors = ThemeManager().get_colors()
        sidebar = ctk.CTkFrame(parent, width=200, fg_color=colors["sidebar"],
                              corner_radius=0)

        ctk.CTkLabel(
            sidebar, text=self._settings.tr("sessions"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["accent"]
        ).pack(anchor="w", padx=10, pady=(10, 6))

        btn_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        btn_row.pack(fill="x", padx=8)
        ctk.CTkButton(
            btn_row, text="Add New", height=28, font=ctk.CTkFont(size=10),
            command=self._add_session
        ).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(
            btn_row, text="Duplicate", height=28, font=ctk.CTkFont(size=10),
            fg_color=colors["surface_alt"], text_color=colors["accent"],
            hover_color=colors["border"],
            command=self._dup_session
        ).pack(side="left", expand=True, fill="x", padx=(3, 0))

        ctk.CTkButton(
            sidebar, text="▶▶  Run All", height=30,
            fg_color=colors["button_ok"], hover_color="#43A047",
            command=self._run_all
        ).pack(fill="x", padx=8, pady=(6, 6))

        self._sessions_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent")
        self._sessions_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        return sidebar

    def _build_statusbar(self) -> None:
        colors = ThemeManager().get_colors()
        bar = ctk.CTkFrame(self, height=28, fg_color=colors["sidebar"],
                          corner_radius=0)
        bar.pack(fill="x", side="bottom")
        self._status_label = ctk.CTkLabel(
            bar, text="  " + self._settings.tr("ready"),
            font=ctk.CTkFont(size=10), text_color=colors["success"])
        self._status_label.pack(side="left", pady=4)
        version = self._settings.get("app", "version") or "1.0.0"
        ctk.CTkLabel(
            bar, text=f"CEA Calculator Pro  v{version}  ",
            font=ctk.CTkFont(size=10), text_color=colors["text_secondary"]
        ).pack(side="right")

    # ── Session management ───────────────────────────────────────────
    def _add_session(self, formulation: Optional[Formulation] = None) -> Session:
        session = Session()
        if formulation:
            session.formulation = formulation
            session.name = formulation.name
        self._sessions.append(session)
        self._select_session(session)
        self._rebuild_sessions_sidebar()
        return session

    def _dup_session(self) -> None:
        if not self._active:
            return
        session = Session(self._active.name + " (copy)")
        session.formulation = copy.deepcopy(self._active.formulation)
        self._sessions.append(session)
        self._select_session(session)
        self._rebuild_sessions_sidebar()

    def _remove_session(self, session: Session) -> None:
        if len(self._sessions) <= 1:
            session.formulation = Formulation()
            session.result = None
            session.status = "pending"
            self._input_panel.clear()
            self._rebuild_sessions_sidebar()
            return
        self._sessions.remove(session)
        if self._active is session:
            self._select_session(self._sessions[-1])
        self._rebuild_sessions_sidebar()

    def _select_session(self, session: Session) -> None:
        if self._active:
            self._active.formulation = self._input_panel.get_formulation()
        self._active = session
        self._input_panel.load_formulation(session.formulation)
        if session.has_result():
            self._show_welcome(False)
            self._results_panel.show_result(session.result, self._current_units())
        self._rebuild_sessions_sidebar()

    def _rebuild_sessions_sidebar(self) -> None:
        for child in self._sessions_scroll.winfo_children():
            child.destroy()
        colors = ThemeManager().get_colors()
        for session in self._sessions:
            active = session is self._active
            row = ctk.CTkFrame(
                self._sessions_scroll, fg_color=(
                    colors["surface_alt"] if active else "transparent"),
                corner_radius=6,
                border_width=2 if active else 0,
                border_color=session.color)
            row.pack(fill="x", pady=2)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(
                top, text="●", text_color=session.color, width=14
            ).pack(side="left")
            name_label = ctk.CTkLabel(
                top, text=session.name, anchor="w",
                font=ctk.CTkFont(size=10, weight="bold" if active else "normal"))
            name_label.pack(side="left", fill="x", expand=True)
            name_label.bind("<Button-1>", lambda e, s=session: self._select_session(s))
            row.bind("<Button-1>", lambda e, s=session: self._select_session(s))

            btn_row = ctk.CTkFrame(row, fg_color="transparent")
            btn_row.pack(fill="x", padx=6, pady=(0, 4))
            ctk.CTkButton(
                btn_row, text="Run", width=44, height=22, font=ctk.CTkFont(size=9),
                command=lambda s=session: self._run_session(s)
            ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(
                btn_row, text="Del", width=40, height=22, font=ctk.CTkFont(size=9),
                fg_color=colors["button_danger"], hover_color="#EF5350",
                command=lambda s=session: self._remove_session(s)
            ).pack(side="left")
            status_text = {"pending": "", "running": "⏳", "done": "✓",
                          "error": "✗"}.get(session.status, "")
            if status_text:
                ctk.CTkLabel(btn_row, text=status_text, width=20).pack(side="left")

    # ── Validation ───────────────────────────────────────────────────
    def _on_validate(self) -> None:
        formulation = self._input_panel.get_formulation()
        self._on_validate_from_panel(formulation)

    def _on_validate_from_panel(self, formulation: Formulation) -> None:
        result = self._validator.validate(
            formulation, check_cea_path=True,
            cea_available=self._executor.available())
        self._input_panel.show_validation(
            result.passed, result.errors, result.warnings)
        if result.passed:
            self._set_status("✓  " + self._settings.tr("validation_ok"))
        else:
            self._set_status("✗  " + "; ".join(result.errors), error=True)

    # ── Calculate ────────────────────────────────────────────────────
    def _on_calculate(self) -> None:
        formulation = self._input_panel.get_formulation()
        if self._active:
            self._active.formulation = formulation
        self._run_session_with_formulation(
            self._active or self._add_session(), formulation)

    def _on_calculate_from_panel(self, formulation: Formulation) -> None:
        self._on_calculate()

    def _run_all(self) -> None:
        for session in self._sessions:
            self._run_session(session)

    def _run_session(self, session: Session) -> None:
        self._run_session_with_formulation(session, session.formulation)

    def _run_session_with_formulation(
            self, session: Session, formulation: Formulation
    ) -> None:
        result = self._validator.validate(
            formulation, check_cea_path=True,
            cea_available=self._executor.available())
        self._input_panel.show_validation(
            result.passed, result.errors, result.warnings)
        if not result.passed:
            self._set_status("✗  Pre-flight failed. Fix errors first.", error=True)
            messagebox.showwarning(
                self._settings.tr("pre_flight"), "\n".join(result.errors))
            return

        session.status = "running"
        self._rebuild_sessions_sidebar()
        self._set_status(f"Running: {session.name}…")
        self._input_panel.set_calculate_enabled(False)
        self._run_btn.configure(state="disabled")
        self._show_welcome(False)
        self._results_panel.log(f"▶  {session.name}")

        worker = CEAWorker(self._executor)
        worker.start(formulation, mode=self._engine_mode)
        self.after(100, lambda: self._poll_worker(worker, session))

    def _poll_worker(self, worker: CEAWorker, session: Session) -> None:
        """Poll the worker's queue on the Tk main thread (never from worker thread)."""
        drained_result = False
        try:
            while True:
                message = worker.queue.get_nowait()
                if message.kind == "log":
                    self._results_panel.log(str(message.payload))
                elif message.kind == "error":
                    self._on_engine_error(str(message.payload))
                elif message.kind == "result":
                    self._on_result(message.payload, session)
                    drained_result = True
        except Exception:
            pass  # queue empty

        if worker.is_running() and not drained_result:
            self.after(100, lambda: self._poll_worker(worker, session))

    def _on_result(self, result: CEAResult, session: Session) -> None:
        session.result = result
        session.status = "done" if result.success else "error"
        self._rebuild_sessions_sidebar()
        self._input_panel.set_calculate_enabled(True)
        self._run_btn.configure(state="normal")

        if result.success:
            self._show_welcome(False)
            self._results_panel.show_result(result, self._current_units())
            done_sessions = [s for s in self._sessions if s.has_result()]
            done_results = [s.result for s in done_sessions]
            done_formulations = [s.formulation for s in done_sessions]
            self._results_panel.update_plots(done_results, done_formulations)
            self._set_status(
                f"✓  {session.name}   Isp={result.isp_m_s:.0f} m/s   "
                f"C*={result.cstar_m_s:.0f} m/s   Tc={result.t_chamber_k:.0f} K")
        else:
            self._set_status(f"✗  {result.error_message}", error=True)

    def _on_engine_error(self, message: str) -> None:
        self._input_panel.set_calculate_enabled(True)
        self._run_btn.configure(state="normal")
        self._set_status("✗  Engine Error", error=True)
        messagebox.showerror("Engine Execution Error", message)

    # ── INP file I/O ─────────────────────────────────────────────────
    def _on_save_inp_request(self, formulation: Formulation) -> None:
        self._save_inp()

    def _save_inp(self) -> None:
        formulation = self._input_panel.get_formulation()
        default_name = (formulation.name or "run").replace(" ", "_") + ".inp"
        path = filedialog.asksaveasfilename(
            title="Save .inp File", defaultextension=".inp",
            initialfile=default_name,
            filetypes=[("CEA Input", "*.inp"), ("All files", "*.*")])
        if not path:
            return
        try:
            INPBuilder.save(formulation, path)
            self._set_status(f"✓  Saved: {path}")
            self._results_panel.log(f"💾  Saved {path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _load_inp(self) -> None:
        path = filedialog.askopenfilename(
            title="Load .inp File",
            filetypes=[("CEA Input", "*.inp"), ("All files", "*.*")])
        if not path:
            return
        try:
            formulation = INPBuilder.parse_file(path)
            self._add_session(formulation)
            self._set_status(f"✓  Loaded: {os.path.basename(path)}")
            self._results_panel.log(f"📂  Loaded {path}")
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))

    def _load_preset(self, preset: dict) -> None:
        formulation = Formulation()
        formulation.name = preset["name"]
        formulation.oxidizer_name = preset["oxidizer"]["name"]
        formulation.oxidizer_temperature_k = preset["oxidizer"]["temperature"]
        formulation.oxidizer_weight_pct = preset["oxidizer"]["weight"]
        formulation.fuel_name = preset["fuel"]["name"]
        formulation.fuel_temperature_k = preset["fuel"]["temperature"]
        formulation.fuel_weight_pct = preset["fuel"]["weight"]
        formulation.chamber_pressure_bar = preset["chamber_pressure"]
        formulation.of_ratio = preset["of_ratio"]
        formulation.exit_pressure_bar = preset["exit_pressure"]
        formulation.area_ratio = preset["area_ratio"]
        formulation.tcest_k = preset.get("tcest", 3800)
        self._add_session(formulation)

    # ── Export ──────────────────────────────────────────────────────
    def _export_csv(self) -> None:
        done = [s for s in self._sessions if s.has_result()]
        if not done:
            messagebox.showinfo("No Results", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export CSV", defaultextension=".csv",
            initialfile="cea_results.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(["Session", "Parameter", "Value", "Unit"])
            for session in done:
                for row in session.result.to_table_rows(self._current_units()):
                    writer.writerow([session.name, row[0], row[1], row[2]])
        self._set_status(f"✓  Exported: {path}")

    def _export_excel(self) -> None:
        """
        Export all completed sessions to a styled Excel workbook: a
        Summary sheet comparing every session side-by-side, plus one
        sheet per session with its performance dashboard image (the
        same chart shown in the Plots tab) embedded above bold-header,
        bordered, alternating-row-shaded data tables.
        """
        done = [s for s in self._sessions if s.has_result()]
        if not done:
            messagebox.showinfo("No Results", "Run a calculation first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Plots & Results to Excel", defaultextension=".xlsx",
            initialfile="cea_results.xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")])
        if not path:
            return

        self._set_status("Building Excel workbook…")
        self.update_idletasks()
        try:
            from core.excel_exporter import ExcelExporter, SessionExport
            units = self._current_units()
            sessions_export = []
            for session in done:
                png_bytes = self._results_panel.render_dashboard_png(
                    [session.result], [session.formulation])
                sessions_export.append(SessionExport(
                    name=session.name, result=session.result,
                    units=units, dashboard_png=png_bytes))
            ExcelExporter().export(sessions_export, path)
            self._set_status(f"✓  Excel workbook saved: {path}")
            self._results_panel.log(
                f"📊  Exported {len(sessions_export)} session(s) to "
                f"Excel with embedded plots: {path}")
        except ImportError:
            messagebox.showerror(
                "Missing Dependency",
                "Excel export requires 'openpyxl' and 'Pillow'.\n"
                "Install with: pip install openpyxl Pillow")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))
            self._set_status("✗  Excel export failed", error=True)

    def _export_research_report(self) -> None:
        """
        Export the active session as a research-grade, 8-sheet
        workbook: Dashboard, Performance Parameters, Exit Composition,
        Expansion Data, Thermodynamic Properties, Sensitivity
        Analysis, Session Metadata, and Validation & References —
        with native Excel charts and a literature comparison against
        a matching historical reference engine.
        """
        if not self._active or not self._active.has_result():
            messagebox.showinfo(
                "No Results", "Run a calculation on the active session first.")
            return
        default_name = (self._active.name or "report").replace(" ", "_") + "_research.xlsx"
        path = filedialog.asksaveasfilename(
            title="Export Research-Grade Report", defaultextension=".xlsx",
            initialfile=default_name, filetypes=[("Excel Workbook", "*.xlsx")])
        if not path:
            return

        self._set_status("Building research-grade report…")
        self.update_idletasks()
        try:
            from core.research_report_exporter import ResearchReportExporter, SessionRecord
            all_sessions = [
                SessionRecord(name=s.name, formulation=s.formulation, result=s.result)
                for s in self._sessions if s.has_result()
            ]
            version = self._settings.get("app", "version") or "1.0.0"
            ResearchReportExporter().export(
                self._active.result, self._active.formulation,
                all_sessions, path, software_version=version)
            self._set_status(f"✓  Research report saved: {path}")
            self._results_panel.log(f"📑  Exported research-grade report: {path}")
        except ImportError:
            messagebox.showerror(
                "Missing Dependency",
                "Research report export requires 'xlsxwriter' and 'pandas'.\n"
                "Install with: pip install xlsxwriter pandas")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))
            self._set_status("✗  Research report export failed", error=True)

    # ── Tool dialogs ────────────────────────────────────────────────
    def _open_nozzle(self) -> None:
        result = self._active.result if self._active else None
        NozzleDesignerDialog(self, result)

    def _open_tool(self, tool_key: str) -> None:
        from core.analysis_tools import TOOL_REGISTRY
        from ui.dialogs.tool_dialog import ToolDialog
        spec = TOOL_REGISTRY.get(tool_key)
        if not spec:
            messagebox.showerror("Tool Not Found", f"Unknown tool: {tool_key}")
            return
        result = self._active.result if self._active else None
        formulation = self._active.formulation if self._active else None
        ToolDialog(self, spec, result, formulation)

    def _open_import_database(self) -> None:
        from ui.dialogs.import_database_dialog import ImportDatabaseDialog
        ImportDatabaseDialog(self, on_imported=self._on_database_imported)

    def _on_database_imported(self) -> None:
        self._results_panel.log(
            f"📥  Database updated: {len(self._db.imported_species())} "
            f"imported species, {len(self._db.all_species_pool())} total "
            "in 'All Species' pool.")

    def _on_engine_mode_changed(self, value: str) -> None:
        mode_map = {"Auto": "auto", "CEA Python": "CEA Python", "FCEA2 Only": "fcea2"}
        self._engine_mode = mode_map.get(value, "auto")
        self._results_panel.log(f"⚙  Engine mode: {value}")
        if self._engine_mode == "fcea2" and not self._executor.available():
            messagebox.showwarning(
                "FCEA2 Not Configured",
                "Engine mode is set to 'FCEA2 Only' but FCEA2.exe is not "
                "configured. Calculations will fail until you set its path "
                "in Settings, or switch back to 'Auto' / 'CEA Python'.")

    def _open_unit_converter(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Unit Converter")
        dialog.geometry("420x320")
        ThemeManager().apply(dialog)
        rows = [
            ("1 bar", "= 14.504 psi = 0.1 MPa"),
            ("T(K)", "= T(°C) + 273.15"),
            ("1 kN", "= 224.81 lbf = 1000 N"),
            ("Isp(s)", "= Isp(m/s) / 9.80665"),
            ("1 in", "= 25.4 mm"),
            ("1 lb", "= 0.4536 kg"),
        ]
        for label, conversion in rows:
            row = ctk.CTkFrame(dialog, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=label, width=100, anchor="w",
                        font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=conversion, anchor="w").pack(side="left")
        ctk.CTkButton(dialog, text="Close", command=dialog.destroy).pack(
            fill="x", padx=12, pady=12)

    # ── Settings ────────────────────────────────────────────────────
    def _open_settings(self) -> None:
        SettingsDialog(self, on_saved=self._on_settings_saved)

    def _on_settings_saved(self) -> None:
        self._executor = CEAExecutor(
            fcea2_exe=self._settings.fcea2_exe(),
            work_dir=self._settings.cea_folder())
        self._refresh_cea_status()
        self._results_panel.log("⚙  Settings saved.")

    def _set_language(self, lang: str) -> None:
        self._settings.set_language(lang)
        messagebox.showinfo(
            "Language",
            f"Language set to {'English' if lang == 'en' else 'Français'}.\n"
            "New dialogs will use this language immediately. Restart to "
            "fully translate existing menus.")

    # ── Helpers ──────────────────────────────────────────────────────
    def _on_clear_active(self) -> None:
        if self._active:
            self._active.formulation = Formulation()
            self._active.result = None
            self._active.status = "pending"
            self._rebuild_sessions_sidebar()

    def _current_units(self) -> Dict[str, str]:
        return {
            "pressure": self._settings.get("units", "pressure") or "bar",
            "temperature": self._settings.get("units", "temperature") or "K",
        }

    def _refresh_cea_status(self) -> None:
        colors = ThemeManager().get_colors()
        if self._executor.available():
            self._cea_status_label.configure(
                text="CEA: Ready", text_color=colors["success"])
        else:
            self._cea_status_label.configure(
                text="CEA: Fallback Mode", text_color=colors["warning"])

    def _show_welcome(self, show: bool) -> None:
        if show:
            self._results_panel.pack_forget()
            self._welcome_panel.pack(fill="both", expand=True)
        else:
            self._welcome_panel.pack_forget()
            self._results_panel.pack(fill="both", expand=True)

    def _set_status(self, message: str, error: bool = False) -> None:
        colors = ThemeManager().get_colors()
        self._status_label.configure(
            text=f"  {message}",
            text_color=colors["error"] if error else colors["success"])

    def _show_about(self) -> None:
        from core.analysis_tools import TOOL_REGISTRY
        messagebox.showinfo(
            "About CEA Calculator Pro",
            "CEA Calculator Pro  v1.1.0\n\n"
            "Strict MVC architecture (NASA_CEA_PROFESSIONAL_STANDARD):\n"
            "  • Data Layer: Formulation, CEAResult, SpeciesDatabase\n"
            "  • Logic Layer: INPBuilder, OUTParser, CEAExecutor,\n"
            "    FallbackCalculator, CEAWorker (threaded), analysis_tools\n"
            "  • UI Layer: customtkinter 5.2.0\n\n"
            f"Species: {len(self._db.all_oxidizers())} curated oxidizers, "
            f"{len(self._db.all_fuels())} curated fuels, "
            f"{len(self._db.all_species_pool())} total in All Species pool.\n"
            f"Analysis tools: {len(TOOL_REGISTRY)} across 6 categories.\n"
            "Engine modes: Auto / Fallback / FCEA2 Only.\n\n"
            "Author: Oukil Khaled Ibn Elwalid")

    def _on_close(self) -> None:
        self._settings.set("window", "width", value=self.winfo_width())
        self._settings.set("window", "height", value=self.winfo_height())
        self._settings.save()
        self._shutting_down = True
        self.destroy()

    def report_callback_exception(self, exc, val, tb) -> None:
        """
        Override Tk's default handler to silence a known, harmless
        customtkinter quirk: its internal ScalingTracker schedules
        periodic ``after()`` callbacks (DPI scaling / dimension checks)
        against the root's Tcl interpreter that are not cancelled on
        ``destroy()``. When they later fire against the now-destroyed
        interpreter, Tcl raises "invalid command name ...update" /
        "...check_dpi_scaling" — purely cosmetic shutdown noise with
        zero effect on the running application. Genuine errors are
        still printed normally.
        """
        if getattr(self, "_shutting_down", False) and exc is TclError:
            text = str(val)
            if "invalid command name" in text:
                return
        import traceback
        traceback.print_exception(exc, val, tb)
