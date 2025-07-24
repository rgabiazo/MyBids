"""Simple console spinner for indicating progress in CLI tools."""

from __future__ import annotations

import itertools
import sys
import threading
import time
from typing import Callable, TypeVar

_T = TypeVar("_T")


class Spinner:
    """Thread-based spinner context manager."""

    def __init__(self, message: str = "", interval: float = 0.1) -> None:
        """Initialise the spinner with an optional message and interval."""
        self.message = message
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        # Track displayed length so the line can be erased when finished.
        # ``_line_len`` includes both the optional ``message`` and the spinning
        # character so that ``stop()`` can fully clear the line.
        self._line_len = len(message) + 2

    def _spin(self) -> None:
        """Write the spinning characters until :func:`stop` is called."""
        for ch in itertools.cycle("|/-\\"):
            if self._stop.is_set():
                break
            sys.stderr.write(ch)
            sys.stderr.flush()
            time.sleep(self.interval)
            sys.stderr.write("\b")
            sys.stderr.flush()

    def start(self) -> None:
        """Begin animating the spinner in a background thread."""
        if self.message:
            # Display the message and leave a space for the spinner character
            # so progress feedback remains on a single console line.
            sys.stderr.write(f"{self.message} ")
            sys.stderr.flush()
        self._thread.start()

    def stop(self) -> None:
        """Stop the spinner and clear the console line."""
        self._stop.set()
        self._thread.join()
        # Clear the entire line using an ANSI escape sequence that moves the
        # cursor to the start and clears to the end of the line. Flushing
        # ensures the console is updated immediately.
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def __enter__(self) -> "Spinner":
        """Start the spinner when entering a ``with`` block."""
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Ensure the spinner stops when exiting a ``with`` block."""
        self.stop()


def run_with_spinner(func: Callable[[], _T], message: str, show: bool = True) -> _T:
    """Execute ``func`` while displaying a spinner when ``show`` is True."""
    if not show:
        return func()
    with Spinner(message):
        return func()
