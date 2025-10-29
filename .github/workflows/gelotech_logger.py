import datetime
import sys
from PyQt6.QtWidgets import QTextEdit

_console_widget = None

def register_console_widget(widget: QTextEdit):
    global _console_widget
    _console_widget = widget

def log(msg: str):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    # Write to console widget if present (UI)
    try:
        if _console_widget:
            _console_widget.append(line)
    except Exception:
        pass
    # Always print to stdout for logging in console or logs
    print(line, file=sys.stdout)