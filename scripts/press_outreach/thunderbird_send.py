#!/usr/bin/env python3
"""Trigger Thunderbird to send the frontmost compose window (macOS)."""

from __future__ import annotations

import random
import subprocess
import time


def auto_send_delay_seconds(*, min_seconds: float = 3.0, max_seconds: float = 4.0) -> float:
    return random.uniform(min_seconds, max_seconds)


def trigger_compose_send() -> None:
    """Send the active Thunderbird compose via Cmd+Enter (needs Accessibility permission)."""
    script = """
tell application "Thunderbird" to activate
delay 0.3
tell application "System Events"
    tell process "Thunderbird"
        keystroke return using command down
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", script], check=True)


def wait_and_send(*, min_seconds: float = 3.0, max_seconds: float = 4.0) -> float:
    delay = auto_send_delay_seconds(min_seconds=min_seconds, max_seconds=max_seconds)
    time.sleep(delay)
    trigger_compose_send()
    return delay
