"""Saving the tracker to a JSON file and loading it back (spec.md section 9).

The file is data/tracker.json when the program runs. Times are saved as ISO text like
"2026-11-16T14:05:00", the computer's local time.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path

from tracker import Deadline, Goal, Session, State

VERSION = 1


class StoreProblem(Exception):
    """The saved file can't be read. The message says what to do."""


def _time(value):
    return None if value is None else value.isoformat()


def _read_time(value):
    return None if value is None else datetime.fromisoformat(value)


def to_dict(state):
    """The state as plain data that JSON can hold."""
    return {
        "version": VERSION,
        "first_run": state.first_run.isoformat(),
        "goal": {
            "minutes": state.goal.minutes,
            "period": state.goal.period,
            "set_at": _time(state.goal.set_at),
        },
        "reset_at": _time(state.reset_at),
        "sessions": [
            {"start": _time(s.start), "end": _time(s.end), "last_seen": _time(s.last_seen)}
            for s in state.sessions
        ],
        "deadlines": [{"name": d.name, "due": _time(d.due)} for d in state.deadlines],
    }


def from_dict(data):
    """Rebuild the state from plain data. Raises KeyError, TypeError or ValueError if broken."""
    if data.get("version") != VERSION:
        raise ValueError(f"unknown version {data.get('version')!r}")
    goal = data["goal"]
    return State(
        first_run=date.fromisoformat(data["first_run"]),
        goal=Goal(int(goal["minutes"]), goal["period"], _read_time(goal["set_at"])),
        reset_at=_read_time(data["reset_at"]),
        sessions=[
            Session(_read_time(s["start"]), _read_time(s["end"]), _read_time(s["last_seen"]))
            for s in data["sessions"]
        ],
        deadlines=[Deadline(d["name"], _read_time(d["due"])) for d in data["deadlines"]],
    )


def load(path):
    """Load the saved state, or None if nothing is saved yet (the very first run)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        return from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise StoreProblem(
            f"The saved file {path} is damaged and can't be read ({error.__class__.__name__}). "
            "Nothing was changed. Fix the file, or move it somewhere else to start fresh."
        ) from error


def save(path, state):
    """Save the state. It is written to a temporary file first and then swapped in, so a
    crash in the middle of saving never leaves a half-written file behind.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(to_dict(state), indent=2)  # fails here, before touching any file
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)  # swaps in one step, even on Windows
