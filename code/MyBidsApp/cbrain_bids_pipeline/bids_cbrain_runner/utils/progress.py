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
        self.message = message
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        # Track displayed length so the line can be erased when finished
        self._line_len = len(message) + 2 if message else 2

    def _spin(self) -> None:
        for ch in itertools.cycle("|/-\\"):
            if self._stop.is_set():
                break
            sys.stderr.write(ch)
            sys.stderr.flush()
            time.sleep(self.interval)
            sys.stderr.write("\b")
            sys.stderr.flush()

    def start(self) -> None:
        if self.message:
            sys.stderr.write(f"{self.message} ")
            sys.stderr.flush()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()
        # Clear the spinner line completely
        sys.stderr.write("\r" + " " * self._line_len + "\r")
        if self.message:
            sys.stderr.write("\n")
        sys.stderr.flush()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


def run_with_spinner(func: Callable[[], _T], message: str, show: bool = True) -> _T:
    """Execute ``func`` while displaying a spinner when ``show`` is True."""
    if not show:
        return func()
    with Spinner(message):
        return func()
