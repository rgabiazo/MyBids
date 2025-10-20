from __future__ import annotations

import os
import sys
import pty
import subprocess
from pathlib import Path
from typing import Sequence, Callable, Optional

import structlog

log = structlog.get_logger()


def run_cmd(
    cmd: Sequence[str],
    *,
    capture: bool = False,
    on_stdout: Optional[Callable[[str], None]] = None,
    suppress_final_result_from_live: bool = False,
) -> subprocess.CompletedProcess:
    """Execute an FSL command while preserving interactive output.

    Args:
        cmd: Command vector passed to :func:`subprocess.Popen`.
        capture: When True, capture combined stdout and stderr and return it.
        on_stdout: Optional callback invoked for each completed line of live
            stdout when streaming MCFLIRT. Ignored otherwise.
        suppress_final_result_from_live: When True, hide the trailing "Final
            result" matrix block from the live stream while keeping it in the
            captured output.

    Returns:
        :class:`subprocess.CompletedProcess` describing the execution result.

    Raises:
        subprocess.CalledProcessError: If the command exits with a non-zero status.
    """
    cmd = [str(c) for c in cmd]

    # Ensure MCFLIRT reports progress to the terminal.
    prog = Path(cmd[0]).name if cmd else ""
    if prog == "mcflirt" and "-report" not in cmd:
        cmd.append("-report")

    log.info("run-cmd", cmd=" ".join(cmd))

    # Stream MCFLIRT live even when capture=True.
    stream_live = capture and prog == "mcflirt"

    if stream_live:
        def _write_stream(text: str) -> None:
            if not text:
                return
            try:
                os.write(sys.stdout.fileno(), text.encode("utf-8", errors="replace"))
            except Exception:
                sys.stdout.write(text)
            sys.stdout.flush()

        # Emits completed lines to `on_stdout`, buffering partial lines.
        line_buf = ""

        def _emit(text: str) -> None:
            nonlocal line_buf
            if not text:
                return
            if on_stdout is None:
                _write_stream(text)
                return
            # Normalize and split to lines; deliver completed lines to callback.
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            line_buf += text
            while True:
                nl = line_buf.find("\n")
                if nl == -1:
                    break
                line = line_buf[:nl]
                on_stdout(line)
                line_buf = line_buf[nl + 1:]

        master_fd, slave_fd = pty.openpty()
        captured: list[bytes] = []
        rc = 0
        pending = ""
        suppressed = False
        marker = "Final result:"

        try:
            with subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            ) as p:
                os.close(slave_fd)
                while True:
                    try:
                        chunk = os.read(master_fd, 1024)
                    except OSError:
                        break
                    if not chunk:
                        if p.poll() is not None:
                            break
                        continue

                    captured.append(chunk)
                    pending += chunk.decode("utf-8", errors="replace")

                    if suppress_final_result_from_live:
                        if suppressed:
                            # Do not emit anything after the "Final result" header.
                            continue

                        # Keep back len(marker) bytes to safely detect the header.
                        while True:
                            idx = pending.find(marker)
                            if idx != -1:
                                # Emit up to the start of "Final result", then stop.
                                pre = pending[:idx]
                                if pre:
                                    _emit(pre)
                                pending = pending[idx:]
                                suppressed = True
                                break

                            safe_len = max(0, len(pending) - len(marker))
                            if safe_len == 0:
                                break
                            to_emit = pending[:safe_len]
                            if to_emit:
                                _emit(to_emit)
                            pending = pending[safe_len:]
                    else:
                        # No suppression: emit all buffered text immediately.
                        if pending:
                            _emit(pending)
                            pending = ""

                rc = p.wait()
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass
            os.close(master_fd)

        # Flush any remaining buffered text (only if "Final result" was absent).
        if not suppressed and pending:
            _emit(pending)

        # Flush last partial line to the callback, if any.
        if on_stdout is not None and line_buf:
            on_stdout(line_buf)

        stdout = b"".join(captured).decode("utf-8", errors="replace")
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd, output=stdout)
        result = subprocess.CompletedProcess(cmd, rc, stdout=stdout)
        setattr(result, "streamed", True)
        return result

    if capture:
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as p:
            stdout, _ = p.communicate()
            rc = p.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd, output=stdout)
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout)

    # Try a PTY first – this coaxes interactive progress/banners out of FSL tools.
    try:
        rc = pty.spawn(cmd)
        sys.stdout.write("\n")
        sys.stdout.flush()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)
        return subprocess.CompletedProcess(cmd, rc)
    except Exception:
        # Fall back to raw byte streaming (no line buffering).
        pass

    # Fallback: stream combined stdout+stderr *byte-by-byte*.
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,  # unbuffered pipe
        text=False,  # read bytes, not lines
    ) as p:
        assert p.stdout is not None
        while True:
            chunk = p.stdout.read(1)
            if not chunk:
                if p.poll() is not None:
                    break
                continue
            try:
                os.write(sys.stdout.fileno(), chunk)
            except Exception:
                # If direct fd write fails (no real TTY), decode and print.
                sys.stdout.write(chunk.decode("utf-8", errors="replace"))
            sys.stdout.flush()
        rc = p.wait()

    sys.stdout.write("\n")
    sys.stdout.flush()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)
    return subprocess.CompletedProcess(cmd, rc)


def mcflirt(
    in_file: Path,
    out_file: Path,
    *,
    capture: bool = False,
    on_stdout: Optional[Callable[[str], None]] = None,
    suppress_final_result_from_live: bool = True,
) -> subprocess.CompletedProcess:
    """Run ``mcflirt`` with ``-report`` enabled."""
    return run_cmd(
        ["mcflirt", "-in", str(in_file), "-out", str(out_file), "-report"],
        capture=capture,
        on_stdout=on_stdout,
        suppress_final_result_from_live=suppress_final_result_from_live,
    )


def fslmaths(in_file: Path, op: str, out_file: Path) -> subprocess.CompletedProcess:
    """Invoke ``fslmaths`` with a single operation."""
    return run_cmd(["fslmaths", str(in_file), op, str(out_file)])


def flirt(in_file: Path, ref_file: Path, out_file: Path) -> subprocess.CompletedProcess:
    """Run ``flirt`` to register *in_file* to *ref_file*."""
    return run_cmd(["flirt", "-in", str(in_file), "-ref", str(ref_file), "-out", str(out_file)])


def fslcc(ref_file: Path, in_file: Path) -> subprocess.CompletedProcess:
    """Compute the FSL correlation coefficient between two images."""
    return run_cmd(["fslcc", str(ref_file), str(in_file)])


def bet(in_file: Path, out_file: Path, frac: float) -> subprocess.CompletedProcess:
    """Execute ``bet`` brain extraction with the provided fractional intensity."""
    return run_cmd(["bet", str(in_file), str(out_file), "-f", str(frac)])
