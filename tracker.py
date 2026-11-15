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


# --- Problems the user should be told about ---

class TrackerProblem(Exception):
    """Something the user asked for breaks a rule. The message says why."""


def format_clock(moment):
    """2:05 PM style, in the computer's local time."""
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def _plural(number, word):
    return f"{number} {word}" if number == 1 else f"{number} {word}s"


# --- Amounts typed in a form: the goal and hand-added sessions ---

def parse_amount(hours_text, minutes_text):
    """Hours and minutes typed in a form, as total minutes. Empty boxes count as 0."""
    try:
        hours = int(hours_text.strip() or "0")
        minutes = int(minutes_text.strip() or "0")
    except ValueError:
        raise TrackerProblem("Hours and minutes must be whole numbers, like 1 and 30.") from None
    if hours < 0 or minutes < 0:
        raise TrackerProblem("Hours and minutes can't be negative.")
    if minutes > 59:
        raise TrackerProblem("Minutes must be from 0 to 59.")
    return hours * 60 + minutes


def new_state(goal_minutes, period, now):
    """The tracker the very first time it runs, with its first goal (spec 1)."""
    return State(first_run=now.date(), goal=_checked_goal(goal_minutes, period, now))


def set_goal(state, goal_minutes, period, now):
    """Change the goal. The new goal counts from 0, starting now (spec 1)."""
    state.goal = _checked_goal(goal_minutes, period, now)


def _checked_goal(goal_minutes, period, now):
    if period not in PERIODS:
        raise TrackerProblem("Please choose Daily, Weekly, Monthly or Yearly.")
    return Goal(goal_minutes, period, now)


def reset(state, now):
    """The Reset button: progress starts again from 0 now. Nothing is deleted (spec 7)."""
    state.reset_at = now


# --- Adding a session by hand (spec.md section 3) ---

MAX_SESSION_MINUTES = 24 * 60


def add_manual_session(state, day, start_time, minutes, now):
    """Add a finished session that started on `day` at `start_time` and lasted `minutes`."""
    if minutes < 1:
        raise TrackerProblem("A session must be at least 1 minute long.")
    if minutes > MAX_SESSION_MINUTES:
        raise TrackerProblem("A session can't be longer than 24 hours.")
    if day < state.first_run:
        raise TrackerProblem(
            f"That day is before you started using the tracker ({state.first_run:%b} {state.first_run.day})."
        )
    start = datetime.combine(day, start_time)
    end = start + timedelta(minutes=minutes)
    if end > now:
        raise TrackerProblem(
            f"A session can't end in the future. It would end at {format_clock(end)}"
            f"{'' if end.date() == now.date() else f' on {end:%b} {end.day}'}, "
            f"but it's {format_clock(now)} now."
        )
    session = Session(start, end)
    state.sessions.append(session)
    return session


# --- The clock (spec.md section 3) ---

CHECK_IN_SECONDS = 30  # how often the open page says "still here"
GONE_AFTER_SECONDS = 90  # no check-in for longer than this = the tab was closed


def running_session(state):
    """The session whose clock is running, or None."""
    for session in state.sessions:
        if session.end is None:
            return session
    return None


def start_clock(state, now):
    """Start a running session now. Only one clock can run at a time."""
    if running_session(state) is not None:
        raise TrackerProblem("A clock is already running. Stop it first.")
    session = Session(now, None, last_seen=now)
    state.sessions.append(session)
    return session


def check_in(state, now):
    """The open page says "still here". Returns False if no clock is running."""
    session = running_session(state)
    if session is None:
        return False
    session.last_seen = now
    return True


def stop_clock(state, now):
    """The Stop button: the running session ends now."""
    session = running_session(state)
    if session is None:
        raise TrackerProblem("No clock is running.")
    session.end = now
    return session


def close_abandoned(state, now):
    """End a running session whose tab was closed, at its last check-in (spec 3).

    Called before anything else on every page load. A session that ends up 0 seconds
    long (closed before its first check-in) is removed. Returns True if one was closed.
    """
    session = running_session(state)
    if session is None:
        return False
    last = session.last_seen or session.start
    if (now - last).total_seconds() <= GONE_AFTER_SECONDS:
        return False
    session.end = last
    if session.end <= session.start:
        state.sessions.remove(session)
    return True


# --- Deadlines (spec.md section 6) ---

def add_deadline(state, name, day, time=None):
    """Add a named deadline. Without a time it means 11:59 PM that day."""
    name = name.strip()
    if not name:
        raise TrackerProblem("Please give the deadline a name, like CSC 300 final.")
    if len(name) > 60:
        raise TrackerProblem("Please keep the deadline name to 60 characters or less.")
    due = datetime.combine(day, time) if time is not None else datetime(day.year, day.month, day.day, 23, 59)
    deadline = Deadline(name, due)
    state.deadlines.append(deadline)
    return deadline


def remove_deadline(state, index):
    """Remove a deadline (only the user does this; nothing is removed on its own)."""
    if not 0 <= index < len(state.deadlines):
        raise TrackerProblem("That deadline doesn't exist anymore.")
    del state.deadlines[index]


def deadline_text(deadline, now):
    """"CSC 300 final: 5 days left", "...: today", "...: 3 days past deadline"."""
    if now <= deadline.due:
        days = (deadline.due.date() - now.date()).days
        left = "today" if days == 0 else f"{_plural(days, 'day')} left"
        return f"{deadline.name}: {left}"
    past = now - deadline.due
    if past.days >= 1:
        amount = _plural(past.days, "day")
    elif past.seconds >= 3600:
        amount = _plural(past.seconds // 3600, "hour")
    elif past.seconds >= 60:
        amount = _plural(past.seconds // 60, "minute")
    else:
        amount = "less than 1 minute"
    return f"{deadline.name}: {amount} past deadline"


def deadlines_in_order(state):
    """The deadlines, soonest first, with their place in state.deadlines (for removing)."""
    return sorted(enumerate(state.deadlines), key=lambda pair: pair[1].due)
