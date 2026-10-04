from __future__ import annotations

from hashlib import sha256

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from photoalbum.i18n import Translator
from photoalbum.sources import (
    ProjectSource,
    SynologyCredentials,
    SynologyPhotosSource,
)
from photoalbum.gui.synology_browser_auth import authenticate_synology_browser


class SynologySourceDialog(QDialog):
    """Acquire an ephemeral browser session, then select an album."""

    def __init__(
        self,
        translator: Translator,
        parent=None,
        *,
        provider_factory=None,
        browser_authenticator=None,
        existing_source: ProjectSource | None = None,
    ):
        super().__init__(parent)
        self._translator = translator
        self._provider_factory = provider_factory or SynologyPhotosSource
        # Kept temporarily for deterministic compatibility tests.
        # Production authentication uses the DSM WebAPI directly.
        self._browser_authenticator = browser_authenticator
        self._existing_source = existing_source
        self._connected_base_url: str | None = None
        self._api_path: str | None = None
        self.provider = None
        self.source = None
        self.setWindowTitle(translator.tr("source.synology.title"))

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://nas.example/")

        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.otp_edit = QLineEdit()

        self.verify_tls_checkbox = QCheckBox(
            translator.tr("source.synology.verify_tls")
        )
        self.verify_tls_checkbox.setChecked(True)

        if existing_source is not None:
            self.url_edit.setText(
                str(existing_source.config.get("base_url", ""))
            )
            self.username_edit.setText(
                str(existing_source.config.get("username", ""))
            )
            self.verify_tls_checkbox.setChecked(
                bool(existing_source.config.get("verify_tls", True))
            )

        form.addRow(translator.tr("source.synology.url"), self.url_edit)
        form.addRow(
            translator.tr("source.synology.username"),
            self.username_edit,
        )
        form.addRow(
            translator.tr("source.synology.password"),
            self.password_edit,
        )
        form.addRow(
            translator.tr("source.synology.otp"),
            self.otp_edit,
        )
        form.addRow("", self.verify_tls_checkbox)
        layout.addLayout(form)

        self.connect_button = QPushButton(
            translator.tr(
                "source.synology.reconnect"
                if existing_source is not None
                else "source.synology.connect"
            )
        )
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)
        self.status_label = QLabel(
            translator.tr("source.synology.credentials_memory")
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.album_combo = QComboBox()
        self.album_combo.setEnabled(False)
        self.album_combo.setVisible(existing_source is None)
        layout.addWidget(self.album_combo)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._accept_source)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _connect(self) -> None:
        if self.provider is not None:
            try:
                self.provider.close()
            except Exception:
                pass
            self.provider = None
        self.album_combo.clear()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        provider = None
        try:
            if self._browser_authenticator is not None:
                # Temporary compatibility path for the existing deterministic
                # browser-session tests. Production does not enter this branch.
                session = self._browser_authenticator(
                    self.url_edit.text().strip(),
                    self.verify_tls_checkbox.isChecked(),
                    self._translator,
                    self,
                )
                if session is None:
                    self.status_label.setText(
                        self._translator.tr(
                            "source.synology.browser_cancelled"
                        )
                    )
                    return
                provider = self._provider_factory(
                    session.origin,
                    session,
                    verify_tls=self.verify_tls_checkbox.isChecked(),
                )
                connected_base_url = session.origin.rstrip("/")
                api_path = session.api_path
            else:
                connected_base_url = (
                    self.url_edit.text().strip().rstrip("/")
                )
                api_path = (
                    str(
                        self._existing_source.config.get(
                            "api_path",
                            "/webapi/entry.cgi",
                        )
                    )
                    if self._existing_source is not None
                    else "/webapi/entry.cgi"
                )
                provider = self._provider_factory(
                    connected_base_url,
                    SynologyCredentials(
                        username=self.username_edit.text().strip(),
                        password=self.password_edit.text(),
                        otp_code=self.otp_edit.text().strip() or None,
                    ),
                    verify_tls=self.verify_tls_checkbox.isChecked(),
                    api_path=api_path,
                )

            provider.connect()
            albums = (
                []
                if self._existing_source is not None
                else provider.list_collections()
            )
        except Exception as exc:
            if provider is not None:
                try:
                    provider.close()
                except Exception:
                    pass
            self.status_label.setText(
                self._translator.tr("source.synology.connection_error", error=exc)
            )
            return
        self.provider = provider
        self._connected_base_url = connected_base_url
        self._api_path = api_path
        if self._existing_source is not None:
            self.source = self._existing_source
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            self.status_label.setText(
                self._translator.tr("source.synology.reconnected")
            )
            return
        for album in albums:
            label = album.name
            if album.item_count is not None:
                label += f" ({album.item_count})"
            self.album_combo.addItem(label, album)
        self.album_combo.setEnabled(bool(albums))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(albums))
        self.status_label.setText(
            self._translator.tr("source.synology.connected", count=len(albums))
        )

    def _accept_source(self) -> None:
        if self._existing_source is not None and self.provider is not None:
            self.source = self._existing_source
            self.accept()
            return
        album = self.album_combo.currentData()
        if self.provider is None or album is None:
            return
        base_url = self._connected_base_url or self.url_edit.text().strip().rstrip("/")
        identity = getattr(self.provider, "identity", None) or base_url
        digest = sha256(f"{base_url}\0{identity}".encode("utf-8")).hexdigest()[:16]
        config = {
            "base_url": base_url,
            "api_path": self._api_path or "/webapi/entry.cgi",
            "verify_tls": self.verify_tls_checkbox.isChecked(),
        }
        username = self.username_edit.text().strip()
        if username:
            config["username"] = username

        self.source = ProjectSource(
            id=f"synology-{digest}",
            kind="synology-photos",
            name=base_url,
            collection_id=album.id,
            collection_name=album.name,
            config=config,
            provider_label="Synology Photos",
            capabilities=getattr(
                self.provider,
                "capabilities",
                SynologyPhotosSource.capabilities,
            ),
        )
        self.accept()

    def reject(self) -> None:
        if self.provider is not None:
            try:
                self.provider.close()
            except Exception:
                pass
            self.provider = None
        super().reject()
