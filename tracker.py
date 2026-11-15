"""Logic for the study tracker: periods, totals, progress and how time is shown.

Kept apart from Flask (app.py) so it can be tested. Every function that depends on the
current time takes `now` as an argument instead of reading the clock, so tests can pick
any moment. All times are the computer's local time, without a time zone.
"""

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction

PERIODS = ("day", "week", "month", "year")
PERIOD_WORDS = {"day": "Today", "week": "This week", "month": "This month", "year": "This year"}


@dataclass
class Session:
    """One study session. end is None while the clock is running."""

    start: datetime
    end: datetime | None = None
    last_seen: datetime | None = None  # last "still here" from the open page (timer only)


@dataclass
class Goal:
    """How many minutes per period, and when this goal was set."""

    minutes: int
    period: str  # one of PERIODS
    set_at: datetime


@dataclass
class Deadline:
    name: str
    due: datetime


@dataclass
class State:
    """Everything the tracker saves."""

    first_run: date
    goal: Goal
    reset_at: datetime | None = None
    sessions: list = field(default_factory=list)
    deadlines: list = field(default_factory=list)

    def counting_from(self):
        """Progress counts sessions that started at or after this moment (spec 4, 7)."""
        if self.reset_at is not None and self.reset_at > self.goal.set_at:
            return self.reset_at
        return self.goal.set_at


# --- Showing amounts of time (spec.md section 8) ---

def format_duration(minutes):
    """45 -> "45min", 60 -> "1 hour", 600 -> "10 hours", 270 -> "4h 30min"."""
    hours, rest = divmod(minutes, 60)
    if hours == 0:
        return f"{rest}min"
    if rest == 0:
        return "1 hour" if hours == 1 else f"{hours} hours"
    return f"{hours}h {rest}min"


def format_done_vs_goal(done, goal):
    """Done against goal: "4/10 hours", "30/45 min", or "4h 30min / 10 hours"."""
    if goal == 0:
        return format_duration(done)
    if done % 60 == 0 and goal % 60 == 0:
        word = "hour" if goal == 60 else "hours"
        return f"{done // 60}/{goal // 60} {word}"
    if done < 60 and goal < 60:
        return f"{done}/{goal} min"
    return f"{format_duration(done)} / {format_duration(goal)}"


# --- Periods (spec.md section 4) ---

def period_start(period, moment):
    """When the period holding this moment began: midnight today, Monday, the 1st, Jan 1."""
    midnight = datetime(moment.year, moment.month, moment.day)
    if period == "day":
        return midnight
    if period == "week":
        return midnight - timedelta(days=moment.weekday())  # Monday is weekday 0
    if period == "month":
        return datetime(moment.year, moment.month, 1)
    if period == "year":
        return datetime(moment.year, 1, 1)
    raise ValueError(f"unknown period {period!r}")


def next_period_start(period, start):
    """When the period that began at `start` ends (the next one begins)."""
    if period == "day":
        return start + timedelta(days=1)
    if period == "week":
        return start + timedelta(days=7)
    if period == "month":
        return datetime(start.year + start.month // 12, start.month % 12 + 1, 1)
    if period == "year":
        return datetime(start.year + 1, 1, 1)
    raise ValueError(f"unknown period {period!r}")


def previous_period_start(period, start):
    """When the period before the one that began at `start` began."""
    return period_start(period, start - timedelta(seconds=1))


# --- Totals ---

def session_seconds(session, now):
    """How long a session lasted, in seconds. A running one counts up to now."""
    end = session.end if session.end is not None else now
    return max(0, int((end - session.start).total_seconds()))


def minutes_between(sessions, start, end, now, since=None):
    """Whole minutes of sessions that started in [start, end), and at or after `since`.

    Seconds are added up first and cut to whole minutes once, so short sessions are not
    lost to rounding.
    """
    seconds = sum(
        session_seconds(s, now)
        for s in sessions
        if start <= s.start < end and (since is None or s.start >= since)
    )
    return seconds // 60


def percent_of(done, goal):
    """done / goal as a whole %, .5 going up. None when the goal is 0 (no goal)."""
    if goal == 0:
        return None
    return math.floor(Fraction(done * 100, goal) + Fraction(1, 2))


@dataclass
class Progress:
    label: str  # "This week"
    done: int  # minutes
    goal: int  # minutes
    percent: int | None  # None = no goal
    extra: int  # minutes over the goal, 0 if not over


def progress(state, now):
    """Progress in the current period, counting from the goal or the last reset (spec 4)."""
    goal = state.goal
    start = period_start(goal.period, now)
    end = next_period_start(goal.period, start)
    done = minutes_between(state.sessions, start, end, now, since=state.counting_from())
    extra = done - goal.minutes if goal.minutes > 0 and done > goal.minutes else 0
    return Progress(PERIOD_WORDS[goal.period], done, goal.minutes, percent_of(done, goal.minutes), extra)


def past_period_text(state, now):
    """The past-period box: "past week = 4/10 hours" (spec 5).

    Counts only sessions since the goal or reset, so the first period shows 0.
    """
    goal = state.goal
    this_start = period_start(goal.period, now)
    last_start = previous_period_start(goal.period, this_start)
    done = minutes_between(state.sessions, last_start, this_start, now, since=state.counting_from())
    return f"past {goal.period} = {format_done_vs_goal(done, goal.minutes)}"


# --- The list of days (spec.md section 2) ---

@dataclass
class DayRow:
    day: date
    minutes: int
    reached: bool | None  # for a daily goal: did the day reach it? None for other goals


def day_rows(state, now):
    """One row per day from the first run up to today, newest first, empty days included.

    Day totals count every session (history), not just since the goal or reset.
    """
    rows = []
    today = now.date()
    day = today
    while day >= state.first_run:
        start = datetime(day.year, day.month, day.day)
        minutes = minutes_between(state.sessions, start, start + timedelta(days=1), now)
        reached = None
        if state.goal.period == "day":
            reached = minutes >= state.goal.minutes  # a goal of 0 is always reached
        rows.append(DayRow(day, minutes, reached))
        day -= timedelta(days=1)
    return rows


def top_message(state):
    """The easter egg at the top of the page (bullet 7)."""
    return "time to work hard!!" if state.goal.minutes > 0 else "have a great off day!!"
