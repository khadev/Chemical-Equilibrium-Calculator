"""
main.py
=========
CEA Calculator Pro — application entry point.

Exactly one ctk.CTk() root is ever created (MainWindow itself), and it
is visible from the moment it is constructed — there is no withdraw/
splash-Toplevel/deiconify sequence. Two earlier attempts at a branded
splash screen (first via a throwaway second root, then via a withdrawn
root + Toplevel + deiconify handoff) each silently failed to ever show
the window on at least one real Windows machine despite the process
running cleanly to mainloop() with zero exceptions — a failure mode
that cannot be reproduced in a headless Linux/Xvfb test sandbox, since
there is no real window manager there to interact with. Removing that
entire mechanism removes the platform-interaction risk it carried; see
ui/main_window.py for the direct, splash-free construction sequence.
"""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S")

log = logging.getLogger("main")


def main() -> int:
    """Application entry point. Returns process exit code."""
    from core.theme_manager import ThemeManager
    from tools.settings_manager import SettingsManager

    ThemeManager()       # must exist before any CTk widget is created
    settings = SettingsManager()

    from ui.main_window import MainWindow
    app = MainWindow()   # the one and only ctk.CTk() root, visible immediately

    log.info("Application started. CEA: %s",
             "READY" if settings.cea_available() else "FALLBACK")
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
