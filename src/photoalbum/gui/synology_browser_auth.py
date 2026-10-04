from __future__ import annotations

from threading import Lock
from urllib.parse import parse_qs, urlsplit, urlunsplit

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from photoalbum.i18n import Translator
from photoalbum.sources.synology import SynologyBrowserSession, SynologyCookie


_TOKEN_HEADER_NAMES = {"x-syno-token", "x-synotoken", "synotoken"}
_SKIPPED_HEADER_NAMES = {
    "authorization",
    "content-length",
    "content-type",
    "cookie",
    "host",
    "origin",
    "referer",
    "x-requested-with",
    *_TOKEN_HEADER_NAMES,
}
_WEBAPI_SCRIPTS = {"entry.cgi", "query.cgi", "auth.cgi"}


class SynologySessionCapture:
    """Collect only the NAS session data needed by the read-only adapter."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._cookies: dict[tuple[str, str, str], SynologyCookie] = {}
        self._api_url: str | None = None
        self._origin: str | None = None
        self._referer: str | None = None
        self._syno_token: str | None = None
        self._token_header = "X-SYNO-TOKEN"
        self._request_headers: tuple[tuple[str, str], ...] = ()
        self._api_priority = -1

    def add_cookie(self, cookie: SynologyCookie) -> None:
        with self._lock:
            self._cookies[(cookie.name, cookie.domain, cookie.path)] = cookie

    def remove_cookie(self, cookie: SynologyCookie) -> None:
        with self._lock:
            self._cookies.pop((cookie.name, cookie.domain, cookie.path), None)

    def observe_request(
        self,
        url: str,
        headers: dict[str, str],
        first_party_url: str = "",
    ) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return
        path_parts = [part for part in parsed.path.casefold().split("/") if part]
        if len(path_parts) < 2 or path_parts[-2] != "webapi":
            return
        if path_parts[-1] not in _WEBAPI_SCRIPTS:
            return

        normalized_headers = {
            str(name).casefold(): str(value) for name, value in headers.items()
        }
        token_header = next(
            (
                name
                for name in headers
                if str(name).casefold() in _TOKEN_HEADER_NAMES
                and str(headers[name])
            ),
            None,
        )
        token = str(headers[token_header]) if token_header is not None else None
        query = parse_qs(parsed.query)
        if not token:
            for name, values in query.items():
                if name.casefold() == "synotoken" and values and values[0]:
                    token = values[0]
                    token_header = "X-SYNO-TOKEN"
                    break
        # A token-bearing WebAPI request is the reliable evidence that this is
        # the actual Photos session, rather than DSM or an SSO provider.
        if not token:
            return

        origin = normalized_headers.get("origin")
        if not origin or urlsplit(origin).netloc != parsed.netloc:
            origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        referer = normalized_headers.get("referer") or first_party_url
        if not referer or urlsplit(referer).netloc != parsed.netloc:
            referer = origin.rstrip("/") + "/"
        else:
            referer_parts = urlsplit(referer)
            referer = urlunsplit((
                referer_parts.scheme,
                referer_parts.netloc,
                referer_parts.path,
                "",
                "",
            ))
        copied = tuple(
            (name, value)
            for name, value in headers.items()
            if str(name).casefold() not in _SKIPPED_HEADER_NAMES
        )
        api_names = [
            value
            for name, values in query.items()
            if name.casefold() == "api"
            for value in values
        ]
        if any(name.strip('"').startswith("SYNO.Foto") for name in api_names):
            priority = 2
        elif (
            "photo" in urlsplit(referer).path.casefold()
            or len(path_parts) > 2
        ):
            priority = 1
        else:
            priority = 0
        with self._lock:
            if priority < self._api_priority:
                return
            self._api_url = urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, "", "")
            )
            self._origin = origin
            self._referer = referer
            self._syno_token = token
            self._token_header = str(token_header)
            self._request_headers = copied
            self._api_priority = priority

    def is_ready(self) -> bool:
        try:
            self.build_session()
        except ValueError:
            return False
        return True

    def build_session(self) -> SynologyBrowserSession:
        with self._lock:
            if not all(
                (self._api_url, self._origin, self._referer, self._syno_token)
            ):
                raise ValueError(
                    "Open Synology Photos and its Albums view before continuing."
                )
            hostname = urlsplit(self._api_url).hostname or ""
            cookies = tuple(
                cookie
                for cookie in self._cookies.values()
                if _cookie_matches_host(cookie, hostname)
            )
            sid = next(
                (cookie.value for cookie in cookies if cookie.name == "id"),
                None,
            )
            if not sid:
                raise ValueError(
                    "No DSM session cookie was found for the Photos endpoint."
                )
            return SynologyBrowserSession(
                api_url=self._api_url,
                origin=self._origin,
                referer=self._referer,
                sid=sid,
                syno_token=self._syno_token,
                cookies=cookies,
                token_header=self._token_header,
                request_headers=self._request_headers,
            )

    def clear(self) -> None:
        with self._lock:
            self._cookies.clear()
            self._api_url = None
            self._origin = None
            self._referer = None
            self._syno_token = None
            self._request_headers = ()
            self._api_priority = -1


class _RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, capture: SynologySessionCapture, parent=None) -> None:
        super().__init__(parent)
        self._capture = capture

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        headers = {
            _qbytes(name): _qbytes(value)
            for name, value in info.httpHeaders().items()
        }
        self._capture.observe_request(
            info.requestUrl().toString(),
            headers,
            info.firstPartyUrl().toString(),
        )


class _SynologyWebPage(QWebEnginePage):
    def __init__(self, profile, *, verify_tls: bool, parent=None) -> None:
        super().__init__(profile, parent)
        self._verify_tls = verify_tls
        self.certificateError.connect(self._handle_certificate_error)

    def _handle_certificate_error(self, error) -> None:
        if self._verify_tls:
            error.rejectCertificate()
        else:
            error.acceptCertificate()

    def createWindow(self, window_type):
        # DSM/SSO links occasionally request a new tab. Keeping navigation in
        # this one ephemeral view preserves one coherent cookie context.
        return self


class EphemeralBrowserResources:
    """Idempotent cleanup, kept small so cancellation is testable with fakes."""

    def __init__(self, profile, page, view, capture: SynologySessionCapture):
        self.profile = profile
        self.page = page
        self.view = view
        self.capture = capture
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.view.stop()
        except Exception:
            pass
        try:
            self.profile.cookieStore().deleteAllCookies()
        except Exception:
            pass
        self.capture.clear()
        for resource in (self.view, self.page, self.profile):
            try:
                resource.deleteLater()
            except Exception:
                pass


class SynologyBrowserAuthDialog(QDialog):
    """Off-the-record browser used only to acquire a DSM Photos session."""

    def __init__(
        self,
        base_url: str,
        translator: Translator,
        parent=None,
        *,
        verify_tls: bool = True,
    ) -> None:
        super().__init__(parent)
        browser_url = _normalized_base_url(base_url)
        self._translator = translator
        self.session: SynologyBrowserSession | None = None
        self.setWindowTitle(translator.tr("source.synology.browser_title"))
        self.resize(1100, 800)

        self._capture = SynologySessionCapture()
        self._profile = QWebEngineProfile(self)
        self._profile.setHttpCacheType(
            QWebEngineProfile.HttpCacheType.MemoryHttpCache
        )
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self._interceptor = _RequestInterceptor(self._capture, self._profile)
        self._profile.setUrlRequestInterceptor(self._interceptor)
        store = self._profile.cookieStore()
        store.cookieAdded.connect(self._cookie_added)
        store.cookieRemoved.connect(self._cookie_removed)
        store.loadAllCookies()

        self._page = _SynologyWebPage(
            self._profile, verify_tls=verify_tls, parent=self
        )
        self._view = QWebEngineView(self)
        self._view.setPage(self._page)
        self._resources = EphemeralBrowserResources(
            self._profile, self._page, self._view, self._capture
        )

        layout = QVBoxLayout(self)
        instructions = QLabel(
            translator.tr("source.synology.browser_instructions")
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        layout.addWidget(self._view, 1)
        self._status = QLabel(translator.tr("source.synology.browser_waiting"))
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._use_button = QPushButton(
            translator.tr("source.synology.browser_use_session")
        )
        self._use_button.setEnabled(False)
        buttons.addButton(
            self._use_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        self._use_button.clicked.connect(self._use_session)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._update_readiness)
        self._timer.start()
        self._view.load(QUrl(browser_url))

    def _cookie_added(self, cookie: QNetworkCookie) -> None:
        self._capture.add_cookie(_cookie_from_qt(cookie))

    def _cookie_removed(self, cookie: QNetworkCookie) -> None:
        self._capture.remove_cookie(_cookie_from_qt(cookie))

    def _update_readiness(self) -> None:
        ready = self._capture.is_ready()
        self._use_button.setEnabled(ready)
        if ready:
            self._status.setText(
                self._translator.tr("source.synology.browser_ready")
            )

    def _use_session(self) -> None:
        try:
            self.session = self._capture.build_session()
        except ValueError:
            self._status.setText(
                self._translator.tr("source.synology.browser_waiting")
            )
            return
        self.accept()

    def done(self, result: int) -> None:
        self._timer.stop()
        self._resources.close()
        super().done(result)


def authenticate_synology_browser(
    base_url: str,
    verify_tls: bool,
    translator: Translator,
    parent=None,
) -> SynologyBrowserSession | None:
    dialog = SynologyBrowserAuthDialog(
        base_url, translator, parent, verify_tls=verify_tls
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.session


def _cookie_from_qt(cookie: QNetworkCookie) -> SynologyCookie:
    return SynologyCookie(
        name=_qbytes(cookie.name()),
        value=_qbytes(cookie.value()),
        domain=cookie.domain(),
        path=cookie.path() or "/",
        secure=cookie.isSecure(),
    )


def _cookie_matches_host(cookie: SynologyCookie, hostname: str) -> bool:
    domain = cookie.domain.lstrip(".").casefold()
    hostname = hostname.casefold()
    return bool(domain) and (
        hostname == domain or hostname.endswith("." + domain)
    )


def _qbytes(value) -> str:
    return bytes(value).decode("latin-1")


def _normalized_base_url(value: str) -> str:
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid NAS address.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))
