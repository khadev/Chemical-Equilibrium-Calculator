"""
ui/main_window.py — Chemical Equilibrium Calculator
Professional scientific application with Qt standard icons.
"""
from __future__ import annotations
import os
import copy
import logging
import json
from typing import Optional, List

from PySide6.QtCore import Qt, Slot, QSize, QPoint
from PySide6.QtGui import QAction, QKeySequence, QIcon, QFont, QPixmap, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QToolBar, QStatusBar,
    QMessageBox, QFileDialog, QApplication, QMenu,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
    QDialog, QLineEdit, QFormLayout, QStyle, QComboBox
)

from models.data_layer import SpeciesDatabase, ConfigManager, Formulation, UserReactant
from engine.calculation_engine import (
    CEAResult, CEAWorker, INPBuilder
)
from ui.styles import STYLESHEET
from ui.widgets.input_panel import InputPanel
from ui.widgets.results_tabs import ResultsTabs
from ui.widgets.toast import show_toast
from ui.dialogs.user_defined_reactant_dialog import UserDefinedReactantDialog

log = logging.getLogger(__name__)

_PALETTE = [
    "#3F51B5", "#00ACC1", "#43A047", "#FB8C00",
    "#E53935", "#8E24AA", "#00897B", "#F4511E",
]


class Session:
    _n = 0
    def __init__(self, name: str = ""):
        Session._n += 1
        self.id = Session._n
        self.name = name or f"Formulation {Session._n}"
        self.formulation = Formulation()
        self.result: Optional[CEAResult] = None
        self.status = "pending"
        self.color = _PALETTE[(Session._n - 1) % len(_PALETTE)]
        self._worker: Optional[CEAWorker] = None

    def has_result(self) -> bool:
        return self.result is not None and self.result.success


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = ConfigManager()
        self._db = SpeciesDatabase()
        self._sessions: List[Session] = []
        self._active: Optional[Session] = None
        self.setStyleSheet(STYLESHEET)

        self._translations = self._load_translations()

        self._setup()
        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._wire()
        self._add_session()
        self.retranslateUi()
        
        self._input_panel.refresh_saved_udr_list(self._db.get_saved_udrs())
        
        log.info("MainWindow ready. DB: %d ox, %d fuels",
                 len(self._db.oxidizers), len(self._db.fuels))

    def _setup(self) -> None:
        v = self._cfg.get("app", "version") or "1.0.0"
        self.setWindowTitle(f"Chemical Equilibrium Calculator  v{v}")
        self.setMinimumSize(1200, 720)
        w = self._cfg.get("window", "width") or 1400
        h = self._cfg.get("window", "height") or 880
        self.resize(w, h)

    def _load_translations(self) -> dict:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_dir = os.path.join(base_dir, "config")
        trans_path = os.path.join(cfg_dir, "translations.json")
        if not os.path.exists(trans_path):
            trans_path = os.path.join(os.getcwd(), "config", "translations.json")
        try:
            with open(trans_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Could not load translations.json: {e}")
            return {"en": {}, "fr": {}}

    def tr(self, key: str) -> str:
        lang = self._cfg.get("language") or "en"
        lang_dict = self._translations.get(lang, {})
        en_dict = self._translations.get("en", {})
        return lang_dict.get(key, en_dict.get(key, key))

    def retranslateUi(self) -> None:
        if hasattr(self, '_file_menu'):
            self._file_menu.setTitle(self.tr("file"))
        if hasattr(self, '_analysis_menu'):
            self._analysis_menu.setTitle(self.tr("analysis"))
        if hasattr(self, '_tools_menu'):
            self._tools_menu.setTitle(self.tr("tools"))
        if hasattr(self, '_session_menu'):
            self._session_menu.setTitle(self.tr("sessions"))
        if hasattr(self, '_settings_menu'):
            self._settings_menu.setTitle(self.tr("settings"))
        if hasattr(self, '_help_menu'):
            self._help_menu.setTitle(self.tr("help"))
        if hasattr(self, '_status_lbl'):
            self._status_lbl.setText(self.tr("ready"))

    # ------------------------------------------------------------------
    # Helper methods for custom icons (fallback if Qt standard icons not wanted)
    # ------------------------------------------------------------------
    def _create_add_icon(self, color: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(2, 8, 14, 2)
        painter.drawRect(8, 2, 2, 14)
        painter.end()
        return QIcon(pixmap)

    def _create_copy_icon(self, color: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 12, 14, 1, 1)
        painter.setBrush(QBrush(QColor(color).lighter(120)))
        painter.drawRoundedRect(4, 4, 12, 14, 1, 1)
        painter.end()
        return QIcon(pixmap)

    def _create_run_icon(self, color: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        points1 = [QPoint(3, 3), QPoint(10, 9), QPoint(3, 15)]
        painter.drawPolygon(points1)
        points2 = [QPoint(9, 3), QPoint(16, 9), QPoint(9, 15)]
        painter.drawPolygon(points2)
        painter.end()
        return QIcon(pixmap)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _build_menubar(self) -> None:
        mb = self.menuBar()
        mb.setStyleSheet("""
            QMenuBar {
                background: #f8f9fa;
                color: #333333;
                padding: 4px;
                border-bottom: 1px solid #e0e0e0;
            }
            QMenuBar::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #3F51B5;
                color: white;
            }
            QMenu {
                background: #ffffff;
                color: #333333;
                border: 1px solid #e0e0e0;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background: #3F51B5;
                color: white;
            }
        """)
        mb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # File menu
        self._file_menu = mb.addMenu("File")
        
        load_action = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton), "Load .inp", self)
        load_action.triggered.connect(self._load_inp)
        load_action.setShortcut(QKeySequence("Ctrl+O"))
        self._file_menu.addAction(load_action)
        
        save_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "Save .inp", self)
        save_action.triggered.connect(self._save_inp)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        self._file_menu.addAction(save_action)
        
        self._file_menu.addSeparator()
        
        export_csv = QAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), "Export CSV", self)
        export_csv.triggered.connect(self._export_csv)
        export_csv.setShortcut(QKeySequence("Ctrl+E"))
        self._file_menu.addAction(export_csv)
        
        export_excel = QAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), "Export Excel", self)
        export_excel.triggered.connect(self._export_excel)
        self._file_menu.addAction(export_excel)
        
        self._file_menu.addSeparator()
        
        exit_action = QAction(self.style().standardIcon(QStyle.SP_DialogCloseButton), "Exit", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self._file_menu.addAction(exit_action)

        # Analysis menu
        self._analysis_menu = mb.addMenu("Analysis")
        
        calc_action = QAction(self.style().standardIcon(QStyle.SP_MediaPlay), "Calculate", self)
        calc_action.triggered.connect(self._run_active)
        calc_action.setShortcut(QKeySequence("Ctrl+R"))
        self._analysis_menu.addAction(calc_action)
        
        validate_action = QAction(self.style().standardIcon(QStyle.SP_DialogApplyButton), "Validate", self)
        validate_action.triggered.connect(self._validate)
        validate_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        self._analysis_menu.addAction(validate_action)
        
        self._analysis_menu.addSeparator()
        
        batch_action = QAction(self.style().standardIcon(QStyle.SP_FileDialogListView), "Batch Sweep", self)
        batch_action.triggered.connect(self._open_batch)
        self._analysis_menu.addAction(batch_action)
        
        run_all_action = QAction(self._create_run_icon("#6c757d"), "Run All Sessions", self)
        run_all_action.triggered.connect(self._run_all)
        self._analysis_menu.addAction(run_all_action)

        # Tools menu
        self._tools_menu = mb.addMenu("Tools")
        
        nozzle_menu = self._tools_menu.addMenu("🔬 Nozzle & Geometry")
        nozzle_action = nozzle_menu.addAction("Nozzle Designer")
        nozzle_action.triggered.connect(self._open_nozzle)
        nozzle_menu.addAction("Chamber Sizer")
        nozzle_menu.addAction("Contraction Ratio")
        
        thermal_menu = self._tools_menu.addMenu("🔥 Thermal & Cooling")
        thermal_menu.addAction("Heat Transfer (Bartz)")
        thermal_menu.addAction("Regenerative Cooling")
        thermal_menu.addAction("Instability Predictor")
        thermal_menu.addAction("Re-entry Heating")
        
        mission_menu = self._tools_menu.addMenu("🌍 Mission & Performance")
        mission_menu.addAction("Delta-V Calculator")
        mission_menu.addAction("Orbit Insertion ΔV")
        mission_menu.addAction("Staging Optimiser")
        mission_menu.addAction("Thrust Vectoring Loss")
        
        advanced_menu = self._tools_menu.addMenu("📊 Advanced Analysis")
        advanced_menu.addAction("CJ Detonation")
        advanced_menu.addAction("Shock Wave Analysis")
        advanced_menu.addAction("Equivalence Ratio Sweep")
        advanced_menu.addAction("Auto-Ignition Temp")
        advanced_menu.addAction("Sensitivity Analysis")
        advanced_menu.addAction("Design of Experiments")
        advanced_menu.addAction("Composition vs T")
        
        materials_menu = self._tools_menu.addMenu("🧪 Materials & Safety")
        materials_menu.addAction("Material Selector")
        materials_menu.addAction("Erosion Predictor")
        materials_menu.addAction("Toxicity Index")
        
        export_menu = self._tools_menu.addMenu("📝 Export & Scripting")
        export_menu.addAction("LaTeX Generator")
        export_menu.addAction("Python Script")
        unit_conv = export_menu.addAction("Unit Converter")
        unit_conv.triggered.connect(self._unit_converter)
        export_menu.addAction("Export CSV")

        # Session menu
        self._session_menu = mb.addMenu("Session")
        
        add_session = QAction(self._create_add_icon("#6c757d"), "Add Session", self)
        add_session.triggered.connect(self._add_session)
        add_session.setShortcut(QKeySequence("Ctrl+T"))
        self._session_menu.addAction(add_session)
        
        dup_session = QAction(self._create_copy_icon("#6c757d"), "Duplicate Session", self)
        dup_session.triggered.connect(self._dup_session)
        self._session_menu.addAction(dup_session)
        
        clear_session = QAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Clear Active", self)
        clear_session.triggered.connect(self._clear_active)
        clear_session.setShortcut(QKeySequence("Ctrl+Del"))
        self._session_menu.addAction(clear_session)

        # Settings menu
        self._settings_menu = mb.addMenu("Settings")
        
        prefs_action = QAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Preferences", self)
        prefs_action.triggered.connect(self._open_settings)
        prefs_action.setShortcut(QKeySequence("Ctrl+,"))
        self._settings_menu.addAction(prefs_action)
        
        self._settings_menu.addSeparator()
        
        lang_en = QAction("English", self)
        lang_en.triggered.connect(lambda: self._set_lang("en"))
        self._settings_menu.addAction(lang_en)
        
        lang_fr = QAction("Français", self)
        lang_fr.triggered.connect(lambda: self._set_lang("fr"))
        self._settings_menu.addAction(lang_fr)
        
        self._settings_menu.addSeparator()
        
        cea_paths = QAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), "Configure Paths", self)
        cea_paths.triggered.connect(self._open_settings)
        self._settings_menu.addAction(cea_paths)

        # Help menu
        self._help_menu = mb.addMenu("Help")
        
        about_action = QAction(self.style().standardIcon(QStyle.SP_FileDialogInfoView), "About", self)
        about_action.triggered.connect(self._about)
        self._help_menu.addAction(about_action)
        
        shortcuts_action = QAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        self._help_menu.addAction(shortcuts_action)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setIconSize(QSize(28, 28))
        tb.setStyleSheet("""
            QToolBar {
                spacing: 8px;
                padding: 6px;
                background: #f8f9fa;
                border-bottom: 1px solid #e0e0e0;
            }
            QToolButton {
                min-width: 40px;
                min-height: 40px;
                border-radius: 8px;
                background: transparent;
            }
            QToolButton:hover {
                background: #e9ecef;
            }
            QToolButton:pressed {
                background: #dee2e6;
            }
        """)
        self.addToolBar(tb)

        calc_btn = QAction(self.style().standardIcon(QStyle.SP_MediaPlay), "Calculate (Ctrl+R)", self)
        calc_btn.triggered.connect(self._run_active)
        tb.addAction(calc_btn)

        validate_btn = QAction(self.style().standardIcon(QStyle.SP_DialogApplyButton), "Validate (Ctrl+Shift+V)", self)
        validate_btn.triggered.connect(self._validate)
        tb.addAction(validate_btn)

        tb.addSeparator()

        load_btn = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton), "Load .inp (Ctrl+O)", self)
        load_btn.triggered.connect(self._load_inp)
        tb.addAction(load_btn)

        save_btn = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "Save .inp (Ctrl+S)", self)
        save_btn.triggered.connect(self._save_inp)
        tb.addAction(save_btn)

        export_btn = QAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), "Export CSV (Ctrl+E)", self)
        export_btn.triggered.connect(self._export_csv)
        tb.addAction(export_btn)

        tb.addSeparator()

        nozzle_btn = QAction(self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "Nozzle Designer", self)
        nozzle_btn.triggered.connect(self._open_nozzle)
        tb.addAction(nozzle_btn)

        batch_btn = QAction(self.style().standardIcon(QStyle.SP_FileDialogListView), "Batch Sweep", self)
        batch_btn.triggered.connect(self._open_batch)
        tb.addAction(batch_btn)

        tb.addSeparator()

        self._cea_lbl = QLabel("  CEA: Fallback Mode  ")
        self._cea_lbl.setStyleSheet("color:#6c757d; font-weight:bold; padding: 6px; background:#e9ecef; border-radius:6px;")
        self._cea_lbl.setToolTip(self.tr("path_not_configured"))
        tb.addWidget(self._cea_lbl)
        self._refresh_cea_label()

    def _build_central(self) -> None:
        central = QWidget()
        central.setStyleSheet("background: #ffffff;")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background: #e0e0e0; max-width: 1px;")
        root.addWidget(sep)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet("QSplitter::handle { background: #e0e0e0; }")

        self._input_panel = InputPanel(self._db)
        self._input_panel.setMinimumWidth(320)
        self._input_panel.setMaximumWidth(420)
        splitter.addWidget(self._input_panel)

        self._results = ResultsTabs()
        self._results.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._results)
        splitter.setSizes([350, 1050])
        root.addWidget(splitter, 1)

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(240)
        w.setStyleSheet("background: #f8f9fa; border-right: 1px solid #e0e0e0;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        hdr = QLabel("Sessions")
        hdr.setStyleSheet("font-weight:bold; font-size:16px; color:#3F51B5; padding:8px;")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hdr)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._add_btn = QPushButton()
        self._add_btn.setIcon(self._create_add_icon("#6c757d"))
        self._add_btn.setIconSize(QSize(20, 20))
        self._add_btn.setFixedSize(36, 36)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setToolTip("Add new session (Ctrl+T)")
        self._add_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        self._add_btn.clicked.connect(self._add_session)
        btn_row.addWidget(self._add_btn)

        self._dup_btn = QPushButton()
        self._dup_btn.setIcon(self._create_copy_icon("#6c757d"))
        self._dup_btn.setIconSize(QSize(20, 20))
        self._dup_btn.setFixedSize(36, 36)
        self._dup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dup_btn.setToolTip("Duplicate current session")
        self._dup_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        self._dup_btn.clicked.connect(self._dup_session)
        btn_row.addWidget(self._dup_btn)

        self._run_all_btn = QPushButton()
        self._run_all_btn.setIcon(self._create_run_icon("#6c757d"))
        self._run_all_btn.setIconSize(QSize(20, 20))
        self._run_all_btn.setFixedSize(36, 36)
        self._run_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_all_btn.setToolTip("Run all sessions")
        self._run_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        self._run_all_btn.clicked.connect(self._run_all)
        btn_row.addWidget(self._run_all_btn)

        lay.addLayout(btn_row)

        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.Shape.HLine)
        sep_line.setStyleSheet("background: #e0e0e0; max-height: 1px; margin: 8px 0;")
        lay.addWidget(sep_line)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        self._sess_container = QWidget()
        self._sess_container.setStyleSheet("background: transparent;")
        self._sess_lay = QVBoxLayout(self._sess_container)
        self._sess_lay.setContentsMargins(0, 0, 0, 0)
        self._sess_lay.setSpacing(8)
        self._sess_lay.addStretch()
        scroll.setWidget(self._sess_container)
        lay.addWidget(scroll, 1)
        return w

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setStyleSheet("background: #f8f9fa; color: #6c757d;")
        self._status_lbl = QLabel(" Ready")
        self._status_lbl.setStyleSheet("padding: 4px;")
        sb.addWidget(self._status_lbl)
        v = self._cfg.get("app", "version") or "1.0.0"
        sb.addPermanentWidget(QLabel(f"Chemical Equilibrium Calculator v{v}"))

    def _wire(self) -> None:
        ip = self._input_panel
        ip.calculate_requested.connect(self._on_calc_request)
        ip.validate_requested.connect(self._on_validate_request)
        ip.save_inp_requested.connect(self._on_save_inp_request)
        ip.load_inp_requested.connect(self._load_inp)
        ip.clear_requested.connect(self._clear_active)
        ip.udr_add_requested.connect(self._open_udr_dialog)
        self._results.copy_done.connect(lambda msg: show_toast(self, msg))

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------
    def _add_session(self, f: Formulation = None) -> Session:
        s = Session()
        if f:
            s.formulation = f
            s.name = f.name
        self._sessions.append(s)
        self._select(s)
        self._rebuild_sessions()
        return s

    def _dup_session(self) -> None:
        if not self._active:
            return
        s = Session(self._active.name + " (copy)")
        s.formulation = copy.deepcopy(self._active.formulation)
        self._sessions.append(s)
        self._select(s)
        self._rebuild_sessions()

    def _remove_session(self, s: Session) -> None:
        if len(self._sessions) <= 1:
            s.formulation = Formulation()
            s.result = None
            s.status = "pending"
            self._input_panel.clear_ui()
            self._rebuild_sessions()
            return
        self._sessions.remove(s)
        if self._active is s:
            self._select(self._sessions[-1])
        self._rebuild_sessions()

    def _select(self, s: Session) -> None:
        if self._active:
            self._active.formulation = self._input_panel.get_formulation()
        self._active = s
        self._input_panel.load_formulation(s.formulation)
        if s.has_result():
            self._results.show_result(s.result, s.name)
        self._rebuild_sessions()

    def _rebuild_sessions(self) -> None:
        while self._sess_lay.count() > 1:
            item = self._sess_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for s in self._sessions:
            self._sess_lay.insertWidget(self._sess_lay.count() - 1, self._make_sess_widget(s))

    def _make_sess_widget(self, s: Session) -> QWidget:
        active = s is self._active
        w = QWidget()
        w.setMinimumHeight(52)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        bg = "#E8EBF0" if active else "#FFFFFF"
        brd = f"2px solid {s.color}" if active else "1px solid #E8E8E8"
        w.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border: {brd};
                border-radius: 10px;
                margin: 2px;
            }}
        """)
        
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Color indicator dot
        dot = QLabel("●")
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"color:{s.color}; font-size:12px;")
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Session name
        name_label = QLabel(s.name)
        name_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: {'bold' if active else 'normal'};
            color: #333333;
            background: transparent;
        """)
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(name_label, 1)

        # Button container
        button_container = QWidget()
        button_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Run button - USING QT STANDARD ICON (100% reliable)
        run_btn = QPushButton()
        run_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        run_btn.setIconSize(QSize(18, 18))
        run_btn.setFixedSize(32, 32)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.setToolTip("Run calculation")
        run_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(40, 167, 69, 0.12);
            }
        """)
        run_btn.clicked.connect(lambda _, ss=s: self._run_session(ss))
        button_layout.addWidget(run_btn)

        # Delete button - USING QT STANDARD ICON (100% reliable)
        del_btn = QPushButton()
        del_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        del_btn.setIconSize(QSize(18, 18))
        del_btn.setFixedSize(32, 32)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Delete session")
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(220, 53, 69, 0.12);
            }
        """)
        del_btn.clicked.connect(lambda _, ss=s: self._remove_session(ss))
        button_layout.addWidget(del_btn)

        layout.addWidget(button_container, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Make the whole widget clickable to select session
        w.mousePressEvent = lambda e, ss=s: self._select(ss)
        name_label.mousePressEvent = lambda e, ss=s: self._select(ss)
        dot.mousePressEvent = lambda e, ss=s: self._select(ss)
        
        return w

    # ------------------------------------------------------------------
    # Calculation Methods
    # ------------------------------------------------------------------
    def _validate(self) -> None:
        f = self._input_panel.get_formulation()
        vr = self._do_validate(f)
        self._input_panel.show_validation(vr["passed"], vr["errors"], vr["warnings"])
        if vr["passed"]:
            self._status("Validation passed.")
        else:
            self._status("; ".join(vr["errors"]), error=True)

    def _do_validate(self, f: Formulation) -> dict:
        errors, warnings = [], []
        if not f.oxidizer_name:
            errors.append("Oxidizer not selected.")
        elif not self._db.is_oxidizer(f.oxidizer_name):
            errors.append(f"'{f.oxidizer_name}' not in oxidizer database.")
        if not f.fuel_name:
            errors.append("Fuel not selected.")
        elif not self._db.is_fuel(f.fuel_name):
            errors.append(f"'{f.fuel_name}' not in fuel database.")
        if not 1.0 <= f.chamber_pressure <= 1000:
            errors.append(f"Pc={f.chamber_pressure} bar outside [1,1000].")
        if not 0.1 <= f.of_ratio <= 30:
            errors.append(f"O/F={f.of_ratio} outside [0.1,30].")
        if not 1.0 <= f.area_ratio <= 500:
            errors.append(f"Ae/At={f.area_ratio} outside [1,500].")
        if not self._cfg.cea_available():
            warnings.append("FCEA2.exe not configured — fallback will be used.")
        return {"passed": len(errors) == 0, "errors": errors, "warnings": warnings}

    @Slot(object)
    def _on_calc_request(self, f: Formulation) -> None:
        if self._active:
            self._active.formulation = f
        self._run_session_with_formulation(self._active or self._add_session(), f)

    @Slot(object)
    def _on_validate_request(self, f: Formulation) -> None:
        vr = self._do_validate(f)
        self._input_panel.show_validation(vr["passed"], vr["errors"], vr["warnings"])

    def _run_active(self) -> None:
        if self._active:
            self._active.formulation = self._input_panel.get_formulation()
            self._run_session(self._active)

    def _run_all(self) -> None:
        for s in self._sessions:
            if not s.formulation.oxidizer_name:
                s.formulation = self._input_panel.get_formulation()
            self._run_session(s)

    def _run_session(self, s: Session) -> None:
        self._run_session_with_formulation(s, s.formulation)

    def _run_session_with_formulation(self, s: Session, f: Formulation) -> None:
        vr = self._do_validate(f)
        self._input_panel.show_validation(vr["passed"], vr["errors"], vr["warnings"])
        if vr["errors"]:
            self._status("Pre-flight failed.", error=True)
            QMessageBox.warning(self, "Validation Error", "\n".join(vr["errors"]))
            return

        s.status = "running"
        self._rebuild_sessions()
        self._status(f"Running: {s.name}...")
        self._results.log(f"▶ {s.name}")

        worker = CEAWorker(f)
        worker.result_ready.connect(lambda r, ss=s: self._on_result(r, ss))
        worker.data_parsed.connect(self._on_data_parsed)
        worker.engine_error.connect(self._on_engine_error)
        worker.log_message.connect(self._results.log)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        s._worker = worker

    @Slot(object)
    def _on_result(self, r: CEAResult, s: Session) -> None:
        s.result = r
        s.status = "done" if r.success else "error"
        self._rebuild_sessions()
        if r.success:
            units = {
                "pressure": self._cfg.get("units", "pressure") or "bar",
                "temperature": self._cfg.get("units", "temperature") or "K",
                "isp": self._cfg.get("units", "isp") or "m/s",
            }
            self._results.show_result(r, s.name, units)
            self._status(f"✓ {s.name} completed")
        else:
            self._status(f"✗ {r.error_msg}", error=True)

    @Slot(object)
    def _on_data_parsed(self, r: CEAResult) -> None:
        done = [s for s in self._sessions if s.has_result()]
        if not done:
            return
        colors = [s.color for s in done]
        forms = [s.formulation.__dict__ for s in done]
        self._results.update_plots([s.result for s in done], colors, forms)

    @Slot(str)
    def _on_engine_error(self, msg: str) -> None:
        self._status("Engine Error", error=True)
        QMessageBox.critical(self, "Engine Error", msg)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    def _save_inp(self) -> None:
        f = self._input_panel.get_formulation()
        self._on_save_inp_request(f)

    @Slot(object)
    def _on_save_inp_request(self, f: Formulation) -> None:
        name = (f.name or "run").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Save .inp File", f"{name}.inp", "CEA Input (*.inp);;All Files (*)")
        if not path:
            return
        try:
            INPBuilder.save(f, path)
            self._status(f"Saved: {path}")
            self._results.log(f"💾 Saved {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_inp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load .inp File", "", "CEA Input (*.inp);;All Files (*)")
        if not path:
            return
        try:
            f = INPBuilder.parse_file(path)
            s = self._add_session(f)
            self._status(f"Loaded: {os.path.basename(path)}")
            self._results.log(f"📂 Loaded {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _export_csv(self) -> None:
        done = [s for s in self._sessions if s.has_result()]
        if not done:
            QMessageBox.information(self, "No Results", "Run a calculation first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "results.csv", "CSV (*.csv)")
        if not path:
            return
        import csv
        units = {"pressure": "bar", "temperature": "K", "isp": "m/s"}
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Session", "Parameter", "Value", "Unit"])
            for s in done:
                for row in s.result.to_table_rows(units):
                    p, v, u = row[0], row[1], row[2]
                    w.writerow([s.name, p, v, u])
        self._status(f"Exported: {path}")
        show_toast(self, "Exported!")

    def _export_excel(self) -> None:
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.critical(self, "pandas required", "pip install pandas openpyxl")
            return
        done = [s for s in self._sessions if s.has_result()]
        if not done:
            QMessageBox.information(self, "No Results", "Run a calculation first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel", "results.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        units = {"pressure": "bar", "temperature": "K", "isp": "m/s"}
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for s in done:
                rows = s.result.to_table_rows(units)
                df = pd.DataFrame([(r[0], r[1], r[2]) for r in rows], columns=["Parameter", "Value", "Unit"])
                df.to_excel(writer, sheet_name=s.name[:31], index=False)
        self._status(f"Exported: {path}")
        show_toast(self, "Exported!")

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _open_nozzle(self) -> None:
        try:
            from ui.dialogs.nozzle_dialog import NozzleDesignerDialog
            r = self._active.result if self._active else None
            dlg = NozzleDesignerDialog(r, parent=self)
            dlg.exec()
        except ImportError:
            QMessageBox.information(self, "Nozzle Designer", "Coming soon!")

    def _open_batch(self) -> None:
        try:
            from ui.dialogs.batch_sweep_dialog import BatchSweepDialog
            f = self._active.formulation if self._active else Formulation()
            dlg = BatchSweepDialog(f, parent=self)
            dlg.exec()
        except ImportError:
            QMessageBox.information(self, "Batch Sweep", "Coming soon!")

    def _open_udr_dialog(self, preset_reactant: dict = None) -> None:
        if preset_reactant:
            udr_dict = preset_reactant
            udr = UserReactant(
                name=udr_dict.get("name", ""),
                wt=udr_dict.get("wt", 100.0),
                temp_k=udr_dict.get("temp_k", 298.0),
                enthalpy_kj=udr_dict.get("enthalpy_kj", 0.0),
                composition=udr_dict.get("composition", {})
            )
            self._add_udr_to_formulation(udr, udr_dict)
        else:
            dlg = UserDefinedReactantDialog(self)
            if dlg.exec():
                udr = dlg.get_reactant()
                if udr and self._active:
                    udr_dict = {
                        "name": udr.name,
                        "wt": udr.wt,
                        "temp_k": udr.temp_k,
                        "enthalpy_kj": udr.enthalpy_kj,
                        "composition": udr.composition
                    }
                    success, msg = self._db.add_saved_udr(udr_dict)
                    if success:
                        self._input_panel.refresh_saved_udr_list(self._db.get_saved_udrs())
                    self._add_udr_to_formulation(udr, udr_dict)

    def _add_udr_to_formulation(self, udr, udr_dict) -> None:
        self._active.formulation.user_reactants.append(udr_dict)
        self._input_panel.add_udr_row(
            udr.to_inp_line(),
            udr_dict,
            lambda row: self._input_panel.remove_udr_row(row)
        )
        show_toast(self, f"Added {udr.name}")

    def _unit_converter(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Unit Converter")
        dlg.setMinimumSize(450, 350)
        lay = QVBoxLayout(dlg)
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
        t = QTableWidget(6, 3)
        t.setStyleSheet("QTableWidget { background: #ffffff; color: #212121; gridline-color: #e0e0e0; }")
        t.setHorizontalHeaderLabels(["Quantity", "Conversion", "Notes"])
        t.horizontalHeader().setStyleSheet("QHeaderView::section { background: #3F51B5; color: white; }")
        for i, (q, c, n) in enumerate([
            ("1 bar", "= 14.504 psi = 0.1 MPa", ""),
            ("T(K)", "= T(°C) + 273.15", ""),
            ("1 kN", "= 224.81 lbf = 1000 N", ""),
            ("Isp(s)", "= Isp(m/s) / 9.80665", ""),
            ("1 in", "= 25.4 mm", ""),
            ("1 lb", "= 0.4536 kg", ""),
        ]):
            t.setItem(i, 0, QTableWidgetItem(q))
            t.setItem(i, 1, QTableWidgetItem(c))
            t.setItem(i, 2, QTableWidgetItem(n))
        t.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(t)
        close = QPushButton("Close")
        close.setStyleSheet("background:#3F51B5; color:white; font-weight:bold; padding:8px; border-radius:6px; border:none;")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _open_settings(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumWidth(650)
        dlg.setMinimumHeight(500)
        dlg.setStyleSheet("QDialog { background: #ffffff; }")
        lay = QVBoxLayout(dlg)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(15)

        def create_browse_button(text, callback):
            btn = QPushButton(text)
            btn.setFixedWidth(100)
            btn.setMinimumHeight(34)
            btn.setStyleSheet("""
                QPushButton {
                    background: #3F51B5;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 6px 12px;
                    border: none;
                }
                QPushButton:hover { background: #5C6BC0; }
            """)
            btn.clicked.connect(callback)
            return btn

        self._fcea2_edit = QLineEdit(self._cfg.fcea2_exe())
        self._fcea2_edit.setPlaceholderText("Select FCEA2.exe file...")
        self._fcea2_edit.setStyleSheet("QLineEdit { background: white; color: #212121; padding: 6px; border-radius: 4px; border: 1px solid #d0d0d0; }")
        browse_fcea2 = create_browse_button("Browse...", self._browse_fcea2)
        fcea2_layout = QHBoxLayout()
        fcea2_layout.addWidget(self._fcea2_edit, 1)
        fcea2_layout.addWidget(browse_fcea2)
        form.addRow("FCEA2.exe Path:", fcea2_layout)

        self._thermo_edit = QLineEdit(self._cfg.get("paths", "thermo_lib") or "")
        self._thermo_edit.setPlaceholderText("Select thermo.lib file...")
        self._thermo_edit.setStyleSheet("QLineEdit { background: white; color: #212121; padding: 6px; border-radius: 4px; border: 1px solid #d0d0d0; }")
        browse_thermo = create_browse_button("Browse...", lambda: self._browse_file(self._thermo_edit, "Thermo.lib"))
        thermo_layout = QHBoxLayout()
        thermo_layout.addWidget(self._thermo_edit, 1)
        thermo_layout.addWidget(browse_thermo)
        form.addRow("Thermo.lib Path:", thermo_layout)

        self._trans_edit = QLineEdit(self._cfg.get("paths", "trans_lib") or "")
        self._trans_edit.setPlaceholderText("Select trans.lib file...")
        self._trans_edit.setStyleSheet("QLineEdit { background: white; color: #212121; padding: 6px; border-radius: 4px; border: 1px solid #d0d0d0; }")
        browse_trans = create_browse_button("Browse...", lambda: self._browse_file(self._trans_edit, "Trans.lib"))
        trans_layout = QHBoxLayout()
        trans_layout.addWidget(self._trans_edit, 1)
        trans_layout.addWidget(browse_trans)
        form.addRow("Trans.lib Path:", trans_layout)

        self._workdir_edit = QLineEdit(self._cfg.cea_work_dir())
        self._workdir_edit.setPlaceholderText("Select working directory...")
        self._workdir_edit.setStyleSheet("QLineEdit { background: white; color: #212121; padding: 6px; border-radius: 4px; border: 1px solid #d0d0d0; }")
        browse_workdir = create_browse_button("Browse...", lambda: self._browse_folder(self._workdir_edit))
        workdir_layout = QHBoxLayout()
        workdir_layout.addWidget(self._workdir_edit, 1)
        workdir_layout.addWidget(browse_workdir)
        form.addRow("Work Directory:", workdir_layout)

        self._pressure_unit_combo = QComboBox()
        self._pressure_unit_combo.addItems(["bar", "psi", "MPa"])
        self._pressure_unit_combo.setStyleSheet("QComboBox { background: white; color: #212121; padding: 6px; border-radius: 4px; border: 1px solid #d0d0d0; }")
        current_p = self._cfg.get("units", "pressure") or "bar"
        idx = self._pressure_unit_combo.findText(current_p)
        if idx >= 0:
            self._pressure_unit_combo.setCurrentIndex(idx)
        form.addRow("Pressure Unit:", self._pressure_unit_combo)

        self._temp_unit_combo = QComboBox()
        self._temp_unit_combo.addItems(["K", "°C"])
        self._temp_unit_combo.setStyleSheet("QComboBox { background: white; color: #212121; padding: 6px; border-radius: 4px; border: 1px solid #d0d0d0; }")
        current_t = self._cfg.get("units", "temperature") or "K"
        idx = self._temp_unit_combo.findText(current_t)
        if idx >= 0:
            self._temp_unit_combo.setCurrentIndex(idx)
        form.addRow("Temperature Unit:", self._temp_unit_combo)

        lay.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(100)
        save_btn.setStyleSheet("background:#28A745; color:white; font-weight:bold; padding:10px; border-radius:6px; border: none;")
        save_btn.clicked.connect(lambda: self._save_settings(dlg))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet("background:#6c757d; color:white; font-weight:bold; padding:10px; border-radius:6px; border: none;")
        cancel_btn.clicked.connect(dlg.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        lay.addLayout(btn_box)

        dlg.exec()

    def _browse_fcea2(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select FCEA2.exe", "", "Executable (*.exe);;All Files (*)")
        if path:
            self._fcea2_edit.setText(path)

    def _browse_file(self, line_edit: QLineEdit, title: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, f"Select {title}", "", "Library files (*.lib);;All Files (*)")
        if path:
            line_edit.setText(path)

    def _browse_folder(self, line_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Work Directory")
        if path:
            line_edit.setText(path)

    def _save_settings(self, dlg: QDialog) -> None:
        self._cfg.set("paths", "fcea2_exe", self._fcea2_edit.text())
        self._cfg.set("paths", "thermo_lib", self._thermo_edit.text())
        self._cfg.set("paths", "trans_lib", self._trans_edit.text())
        self._cfg.set("paths", "cea_work_dir", self._workdir_edit.text())
        self._cfg.set("units", "pressure", self._pressure_unit_combo.currentText())
        self._cfg.set("units", "temperature", self._temp_unit_combo.currentText())
        self._cfg.save()
        self._refresh_cea_label()
        dlg.accept()
        show_toast(self, "Settings saved!")

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------
    def _set_lang(self, lang: str) -> None:
        self._cfg.set("language", lang)
        self._cfg.save()
        self.retranslateUi()
        show_toast(self, f"Language set to {'English' if lang=='en' else 'Français'}")

    def _refresh_cea_label(self) -> None:
        if self._cfg.cea_available():
            self._cea_lbl.setText("  CEA: Ready  ")
            self._cea_lbl.setStyleSheet("color:#28A745; font-weight:bold; padding:6px; background:#e9ecef; border-radius:6px;")
        else:
            self._cea_lbl.setText("  CEA: Fallback  ")
            self._cea_lbl.setStyleSheet("color:#6c757d; font-weight:bold; padding:6px; background:#e9ecef; border-radius:6px;")

    def _status(self, msg: str, error: bool = False) -> None:
        self._status_lbl.setText(f" {msg}")
        self._status_lbl.setStyleSheet("color: #DC3545;" if error else "color: #28A745;")

    def _about(self) -> None:
        QMessageBox.about(self, "About Chemical Equilibrium Calculator",
                          "<b style='color:#3F51B5;'>Chemical Equilibrium Calculator v1.0.0</b><br><br>"
                          "<b>Professional Chemical Equilibrium Analysis Tool</b><br><br>"
                          "Features:<br>"
                          "• NASA CEA2 Integration<br>"
                          "• Multi-session Management<br>"
                          "• Advanced Visualization<br>"
                          "• User-Defined Reactants<br><br>"
                          "<b>Author:</b> Oukil Khaled Ibn Elwalid")

    def _show_shortcuts(self) -> None:
        QMessageBox.information(self, "Keyboard Shortcuts",
                                "<b>Shortcuts</b><br><br>"
                                "Ctrl+R        - Calculate<br>"
                                "Ctrl+Shift+V  - Validate<br>"
                                "Ctrl+T        - Add new session<br>"
                                "Ctrl+O        - Load .inp file<br>"
                                "Ctrl+S        - Save .inp file<br>"
                                "Ctrl+E        - Export CSV<br>"
                                "Ctrl+Del      - Clear active session<br>"
                                "Ctrl+,        - Open Settings")

    def closeEvent(self, event) -> None:
        self._cfg.set("window", "width", self.width())
        self._cfg.set("window", "height", self.height())
        self._cfg.save()
        event.accept()

    def _clear_active(self) -> None:
        if self._active:
            self._active.formulation = Formulation()
            self._active.result = None
            self._active.status = "pending"
            self._input_panel.clear_ui()
            self._rebuild_sessions()