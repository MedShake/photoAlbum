from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from photoalbum.app import ProjectService


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self._project_service = ProjectService()

        self.setWindowTitle("Photo Album")
        self.resize(1100, 700)

        self._create_actions()
        self._create_menu()
        self._create_content()
        self._create_status_bar()

        self._update_project_state()

    def closeEvent(self, event) -> None:
        self._project_service.close()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        self._new_project_action = QAction(
            "New Project...",
            self,
        )
        self._new_project_action.triggered.connect(
            self._new_project
        )

        self._open_project_action = QAction(
            "Open Project...",
            self,
        )
        self._open_project_action.triggered.connect(
            self._open_project
        )

        self._close_project_action = QAction(
            "Close Project",
            self,
        )
        self._close_project_action.triggered.connect(
            self._close_project
        )

        self._quit_action = QAction(
            "Quit",
            self,
        )
        self._quit_action.triggered.connect(self.close)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        file_menu.addAction(self._new_project_action)
        file_menu.addAction(self._open_project_action)
        file_menu.addAction(self._close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)

    def _create_content(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        self._project_label = QLabel()
        self._project_label.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )

        layout.addWidget(self._project_label)

        source_layout = QHBoxLayout()

        self._source_edit = QLineEdit()
        self._source_edit.setReadOnly(True)

        self._browse_source_button = QPushButton(
            "Choose Source Folder..."
        )
        self._browse_source_button.clicked.connect(
            self._choose_source_directory
        )

        source_layout.addWidget(QLabel("Source folder:"))
        source_layout.addWidget(self._source_edit, 1)
        source_layout.addWidget(self._browse_source_button)

        layout.addLayout(source_layout)

        self._recursive_checkbox = QCheckBox(
            "Include subdirectories"
        )
        self._recursive_checkbox.toggled.connect(
            self._recursive_changed
        )

        layout.addWidget(self._recursive_checkbox)
        layout.addStretch()

        self.setCentralWidget(central_widget)

    def _create_status_bar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

    def _new_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Create Photo Album Project",
            "",
            "Photo Album Project (*.photoalbum)",
        )

        if not path:
            return

        project_path = Path(path)

        if project_path.suffix != ".photoalbum":
            project_path = project_path.with_suffix(
                ".photoalbum"
            )

        try:
            self._project_service.create(project_path)
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._load_project_settings()
        self._update_project_state()

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Photo Album Project",
            "",
            "Photo Album Project (*.photoalbum)",
        )

        if not path:
            return

        try:
            self._project_service.open(Path(path))
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._load_project_settings()
        self._update_project_state()

    def _close_project(self) -> None:
        self._project_service.close()

        self._source_edit.clear()
        self._recursive_checkbox.setChecked(False)

        self._update_project_state()

    def _choose_source_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Source Photo Folder",
        )

        if not directory:
            return

        try:
            self._project_service.set_source_directory(
                Path(directory)
            )
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._source_edit.setText(directory)

    def _recursive_changed(
        self,
        checked: bool,
    ) -> None:
        if not self._project_service.is_open:
            return

        self._project_service.set_recursive_scan(checked)

    def _load_project_settings(self) -> None:
        source_directory = (
            self._project_service.get_source_directory()
        )

        self._source_edit.setText(
            str(source_directory)
            if source_directory is not None
            else ""
        )

        self._recursive_checkbox.setChecked(
            self._project_service.get_recursive_scan()
        )

    def _update_project_state(self) -> None:
        is_open = self._project_service.is_open

        self._close_project_action.setEnabled(is_open)
        self._browse_source_button.setEnabled(is_open)
        self._recursive_checkbox.setEnabled(is_open)

        if is_open:
            project_path = self._project_service.project_path

            self._project_label.setText(
                f"Project: {project_path.name}"
            )

            self.statusBar().showMessage(
                str(project_path)
            )
        else:
            self._project_label.setText(
                "No project open"
            )
            self.statusBar().showMessage("Ready")

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            "Photo Album",
            message,
        )