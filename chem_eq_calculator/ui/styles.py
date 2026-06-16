"""ui/styles.py — Light theme QSS that preserves native controls."""

STYLESHEET = """
/* ============================================================
   MAIN WINDOW
   ============================================================ */
QMainWindow {
    background-color: #F5F5F5;
}

QWidget {
    background-color: #F5F5F5;
}

/* ============================================================
   MENU BAR
   ============================================================ */
QMenuBar {
    background-color: #F5F5F5;
    border-bottom: 1px solid #E0E0E0;
    padding: 2px;
}

QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #3F51B5;
    color: white;
}

QMenu {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #3F51B5;
    color: white;
}

QMenu::separator {
    height: 1px;
    background-color: #E0E0E0;
    margin: 4px 8px;
}

/* ============================================================
   TOOLBAR
   ============================================================ */
QToolBar {
    background-color: #F5F5F5;
    border-bottom: 1px solid #E0E0E0;
    spacing: 4px;
    padding: 4px;
}

QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px;
}

QToolButton:hover {
    background-color: #E8EAF6;
}

QToolButton:pressed {
    background-color: #C5CAE9;
}

/* ============================================================
   STATUS BAR
   ============================================================ */
QStatusBar {
    background-color: #F5F5F5;
    border-top: 1px solid #E0E0E0;
    color: #6C757D;
    padding: 2px 8px;
}

/* ============================================================
   GROUP BOX
   ============================================================ */
QGroupBox {
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #3F51B5;
    background-color: #FFFFFF;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    font-size: 12px;
}

/* ============================================================
   TAB WIDGET
   ============================================================ */
QTabWidget::pane {
    border: 1px solid #E0E0E0;
    border-radius: 0 8px 8px 8px;
    background-color: white;
}

QTabBar::tab {
    background-color: #F0F0F0;
    color: #6C757D;
    padding: 10px 24px;
    border: 1px solid #E0E0E0;
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    margin-right: 2px;
    min-width: 100px;
}

QTabBar::tab:selected {
    background-color: #3F51B5;
    color: white;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #E8EAF6;
    color: #333333;
}

/* ============================================================
   TABLE WIDGET
   ============================================================ */
QTableWidget {
    background-color: white;
    alternate-background-color: #FAFAFA;
    gridline-color: #E0E0E0;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
}

QTableWidget::item {
    padding: 8px 12px;
}

QTableWidget::item:selected {
    background-color: #C5CAE9;
    color: #212121;
}

QHeaderView::section {
    background-color: #3F51B5;
    color: white;
    font-weight: bold;
    padding: 10px;
    border: none;
    border-right: 1px solid #5C6BC0;
}

/* ============================================================
   PUSH BUTTONS - PRIMARY
   ============================================================ */
QPushButton {
    background-color: #3F51B5;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    min-height: 36px;
}

QPushButton:hover {
    background-color: #5C6BC0;
}

QPushButton:pressed {
    background-color: #1A237E;
}

QPushButton:disabled {
    background-color: #BDBDBD;
    color: #757575;
}

/* ============================================================
   PUSH BUTTONS - SPECIAL VARIANTS
   ============================================================ */
QPushButton#btn_run {
    background-color: #2E7D32;
}

QPushButton#btn_run:hover {
    background-color: #388E3C;
}

QPushButton#btn_danger {
    background-color: #E53935;
}

QPushButton#btn_danger:hover {
    background-color: #EF5350;
}

QPushButton#btn_secondary {
    background-color: #E8EAF6;
    color: #212121;
    border: 1px solid #C5CAE9;
}

QPushButton#btn_secondary:hover {
    background-color: #C5CAE9;
    border: 1px solid #3F51B5;
}

/* ============================================================
   SESSION ACTION BUTTONS (transparent with hover)
   ============================================================ */
QPushButton#session_run {
    background-color: transparent;
    border: none;
    border-radius: 6px;
}

QPushButton#session_run:hover {
    background-color: rgba(40, 167, 69, 0.15);
}

QPushButton#session_delete {
    background-color: transparent;
    border: none;
    border-radius: 6px;
}

QPushButton#session_delete:hover {
    background-color: rgba(220, 53, 69, 0.15);
}

/* ============================================================
   LINE EDIT
   ============================================================ */
QLineEdit {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 32px;
    color: #333333;
}

QLineEdit:hover {
    border: 1px solid #3F51B5;
}

QLineEdit:focus {
    border: 2px solid #3F51B5;
}

/* ============================================================
   TEXT EDIT
   ============================================================ */
QTextEdit, QPlainTextEdit {
    background-color: white;
    color: #333333;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 8px;
    font-family: 'Courier New', monospace;
    font-size: 10px;
}

QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #3F51B5;
}

/* ============================================================
   CHECKBOX
   ============================================================ */
QCheckBox {
    spacing: 8px;
    color: #333333;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: white;
}

QCheckBox::indicator:hover {
    border: 1px solid #3F51B5;
}

QCheckBox::indicator:checked {
    background-color: #3F51B5;
    border: 1px solid #3F51B5;
}

/* ============================================================
   SCROLL BARS
   ============================================================ */
QScrollBar:vertical {
    background-color: #F0F0F0;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #C0C0C0;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3F51B5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #F0F0F0;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #C0C0C0;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3F51B5;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ============================================================
   SPLITTER
   ============================================================ */
QSplitter::handle {
    background-color: #E0E0E0;
}

/* ============================================================
   SCROLL AREA
   ============================================================ */
QScrollArea {
    border: none;
    background-color: transparent;
}

/* ============================================================
   LABELS
   ============================================================ */
QLabel#lbl_header {
    font-size: 14px;
    font-weight: bold;
    color: #1A237E;
}

QLabel#status_ok {
    color: #2E7D32;
    font-weight: bold;
}

QLabel#status_error {
    color: #C62828;
    font-weight: bold;
}

/* ============================================================
   COMBOBOX - NATIVE ARROWS PRESERVED
   ============================================================ */
QComboBox {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 32px;
    color: #333333;
}

QComboBox:hover {
    border: 1px solid #3F51B5;
}

QComboBox:focus {
    border: 2px solid #3F51B5;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    selection-background-color: #3F51B5;
    selection-color: white;
    outline: none;
}

/* ============================================================
   SPINBOX - NATIVE ARROWS PRESERVED
   ============================================================ */
QSpinBox, QDoubleSpinBox {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 32px;
    color: #333333;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #3F51B5;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #3F51B5;
}
"""