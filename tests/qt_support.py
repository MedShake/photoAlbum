"""GUI waits that let Python workers and Qt deferred deletion both progress."""
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer


def wait_events(milliseconds: int) -> None:
    # QTest.qWait can hold the GIL while dispatching DeferredDelete. A worker
    # deleting a QObject can then wait for the GIL while the GUI waits for its
    # connection mutex. exec() releases the GIL, like the real application loop.
    application = QCoreApplication.instance()
    assert application is not None
    loop = QEventLoop(application)
    timer = QTimer(loop)
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(milliseconds)
    loop.exec()
    loop.deleteLater()
