from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Photo Album")
        self.resize(1100, 700)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        title = QLabel("Photo Album")
        title.setStyleSheet(
            "font-size: 24px; font-weight: bold;"
        )

        message = QLabel(
            "Create and manage chronological photo albums."
        )

        layout.addWidget(title)
        layout.addWidget(message)
        layout.addStretch()

        self.setCentralWidget(central_widget)

        status_bar = QStatusBar()
        status_bar.showMessage("Ready")
        self.setStatusBar(status_bar)