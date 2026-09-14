"""
GUI package.

Importing a low-level GUI helper must not bootstrap the whole
application. In particular, template renderers may import GUI
workers without importing MainWindow.
"""


def main():
    from .application import main as application_main

    return application_main()


__all__ = [
    "main",
]
