"""
main.py — Chemical Equilibrium Calculator
Entry point: logging, high‑DPI, splash, MainWindow launch.
"""
from __future__ import annotations
import sys
import os
import logging

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S"
)

def main() -> int:
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QPen, QLinearGradient, QBrush

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Chemical Equilibrium Calculator")
    app.setStyle("Fusion")

    # ============================================================
    # BEAUTIFUL SPLASH SCREEN WITH THERMODYNAMIC THEME
    # ============================================================
    pix = QPixmap(600, 380)
    pix.fill(QColor("#0F2027"))  # Dark scientific background
    
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Gradient background (deep blue to teal)
    gradient = QLinearGradient(0, 0, 600, 380)
    gradient.setColorAt(0, QColor("#0F2027"))
    gradient.setColorAt(0.5, QColor("#203A43"))
    gradient.setColorAt(1, QColor("#2C5364"))
    p.fillRect(0, 0, 600, 380, QBrush(gradient))
    
    # Draw decorative hexagon pattern (chemical theme)
    p.setPen(QPen(QColor("#3F51B5"), 1, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    
    # Hexagon 1
    hex_points = []
    center_x, center_y = 150, 120
    for i in range(6):
        angle = i * 60 - 30
        x = center_x + 40 * (angle * 3.14159 / 180)
        y = center_y + 40 * (angle * 3.14159 / 180)
        hex_points.append((x, y))
    for i in range(len(hex_points)):
        p.drawLine(int(hex_points[i][0]), int(hex_points[i][1]), 
                   int(hex_points[(i+1)%len(hex_points)][0]), int(hex_points[(i+1)%len(hex_points)][1]))
    
    # Hexagon 2
    hex_points2 = []
    center_x2, center_y2 = 450, 280
    for i in range(6):
        angle = i * 60
        x = center_x2 + 30 * (angle * 3.14159 / 180)
        y = center_y2 + 30 * (angle * 3.14159 / 180)
        hex_points2.append((x, y))
    for i in range(len(hex_points2)):
        p.drawLine(int(hex_points2[i][0]), int(hex_points2[i][1]), 
                   int(hex_points2[(i+1)%len(hex_points2)][0]), int(hex_points2[(i+1)%len(hex_points2)][1]))
    
    # Draw molecule-like circles (atoms)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#3F51B5"), Qt.BrushStyle.SolidPattern))
    p.drawEllipse(100, 80, 12, 12)
    p.setBrush(QBrush(QColor("#00ACC1"), Qt.BrushStyle.SolidPattern))
    p.drawEllipse(130, 100, 8, 8)
    p.setBrush(QBrush(QColor("#FF4081"), Qt.BrushStyle.SolidPattern))
    p.drawEllipse(85, 110, 6, 6)
    p.setBrush(QBrush(QColor("#4CAF50"), Qt.BrushStyle.SolidPattern))
    p.drawEllipse(470, 260, 10, 10)
    p.setBrush(QBrush(QColor("#FFC107"), Qt.BrushStyle.SolidPattern))
    p.drawEllipse(440, 290, 7, 7)
    
    # Draw connecting lines (bonds)
    p.setPen(QPen(QColor("#3F51B5"), 1.5))
    p.drawLine(100, 86, 130, 100)
    p.drawLine(100, 86, 85, 110)
    p.drawLine(470, 266, 440, 290)
    
    # Main title with chemical flask icon (using text symbol)
    p.setPen(QColor("#FFFFFF"))
    p.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
    p.drawText(190, 95, 380, 50, Qt.AlignmentFlag.AlignLeft, "🌡️ Chemical Equilibrium")
    
    p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    p.drawText(190, 135, 380, 40, Qt.AlignmentFlag.AlignLeft, "Calculator")
    
    # Subtitle with thermodynamic symbols
    p.setPen(QColor("#B0BEC5"))
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Normal))
    p.drawText(190, 170, 380, 30, Qt.AlignmentFlag.AlignLeft, "ΔG = 0  |  K = e^(-ΔG°/RT)  |  PV = nRT")
    
    # Version badge
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#3F51B5"), Qt.BrushStyle.SolidPattern))
    p.drawRoundedRect(190, 195, 100, 26, 13, 13)
    p.setPen(QColor("#FFFFFF"))
    p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    p.drawText(190, 195, 100, 26, Qt.AlignmentFlag.AlignCenter, "v1.0.0")
    
    # Author line
    p.setPen(QColor("#78909C"))
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
    p.drawText(0, 340, 600, 25, Qt.AlignmentFlag.AlignCenter, "by Oukil Khaled Ibn Elwalid")
    
    # Progress bar background
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#1A237E"), Qt.BrushStyle.SolidPattern))
    p.drawRoundedRect(60, 360, 480, 6, 3, 3)
    
    # Progress bar fill (will be updated dynamically)
    p.setBrush(QBrush(QColor("#3F51B5"), Qt.BrushStyle.SolidPattern))
    p.drawRoundedRect(60, 360, 260, 6, 3, 3)
    
    # Draw small decorative elements (temperature gauge)
    p.setPen(QPen(QColor("#3F51B5"), 1.5))
    p.drawArc(490, 55, 30, 30, 0, 360 * 16)
    p.setPen(QPen(QColor("#FF4081"), 2))
    p.drawLine(505, 70, 505, 55)
    p.drawEllipse(502, 48, 6, 6)
    
    p.end()

    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    splash.showMessage("  Loading species database…",
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                       QColor("#3F51B5"))
    app.processEvents()

    from models.data_layer import SpeciesDatabase, ConfigManager
    db = SpeciesDatabase()
    cfg = ConfigManager()
    logging.getLogger(__name__).info(
        "DB: %d oxidizers, %d fuels", len(db.oxidizers), len(db.fuels)
    )

    splash.showMessage("  Building UI…",
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                       QColor("#3F51B5"))
    app.processEvents()

    from ui.main_window import MainWindow
    win = MainWindow()
    splash.finish(win)
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())