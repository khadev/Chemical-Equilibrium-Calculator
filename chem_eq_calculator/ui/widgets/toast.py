"""ui/widgets/toast.py — Toast notification widget."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

class Toast(QLabel):
    def __init__(self, parent: QWidget, message: str, ms: int = 2000):
        super().__init__(f"  {message}  ", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background:rgba(55,71,79,0.92); color:#FFF;"
            " font-size:13px; font-weight:bold;"
            " border-radius:20px; padding:10px 28px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.adjustSize()
        pw, ph = parent.width(), parent.height()
        self.move((pw - self.width())//2, ph - self.height() - 60)
        self.show(); self.raise_()
        QTimer.singleShot(ms, self.deleteLater)

def show_toast(parent: QWidget, msg: str = "Text Copied!", ms: int = 2000):
    Toast(parent, msg, ms)
