"""Temporary idle-sleep protection for bounded live research on macOS."""
from contextlib import contextmanager
import os
import platform
import subprocess


@contextmanager
def keep_awake(enabled=True):
    """Release the assertion on success/failure; parent exit also releases it.

    This prevents idle sleep, not a user-requested sleep or lid closure. Worker
    wall-clock deadlines and interruption accounting remain authoritative.
    """
    process = None
    if enabled and platform.system() == 'Darwin':
        process = subprocess.Popen(
            ['/usr/bin/caffeinate', '-i', '-w', str(os.getpid())],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
    try:
        if process is not None and process.poll() is not None:
            raise RuntimeError('Live research idle-sleep protection could not start')
        yield
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
