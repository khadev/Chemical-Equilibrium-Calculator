from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

class BatchSweepDialog(QDialog):
    def __init__(self, formulation, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Sweep")
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Batch sweep feature coming soon."))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
