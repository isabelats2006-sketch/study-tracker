"""Tests for periods, totals, progress and showing time (spec.md sections 2, 4, 5, 8).

Nov 16, 2026 is a Monday, which several tests rely on.
"""

from datetime import date, datetime, timedelta

import pytest

from tracker import (
    Goal, Session, State, day_rows, format_done_vs_goal, format_duration, minutes_between,
    next_period_start, past_period_text, percent_of, period_start, previous_period_start,
    progress, top_message,
)


def at(text):
    """A local time from short text: at("2026-11-16 14:05")."""
    return datetime.fromisoformat(text)


def session(start, minutes):
    """A finished session that lasted this many minutes."""
    begin = at(start)
    return Session(begin, begin + timedelta(minutes=minutes))


def state(goal_minutes=600, period="week", goal_set="2026-11-16 08:00", sessions=(), reset=None,
          first_run=date(2026, 11, 16)):
    return State(
        first_run=first_run,
        goal=Goal(goal_minutes, period, at(goal_set)),
        reset_at=at(reset) if reset else None,
        sessions=list(sessions),
    )


# --- Showing amounts of time (section 8) ---

@pytest.mark.parametrize(
    "minutes, text",
    [(0, "0min"), (45, "45min"), (60, "1 hour"), (120, "2 hours"), (600, "10 hours"),
     (90, "1h 30min"), (270, "4h 30min"), (61, "1h 1min")],
)
def test_format_duration(minutes, text):
    assert format_duration(minutes) == text


@pytest.mark.parametrize(
    "done, goal, text",
    [
        (240, 600, "4/10 hours"),  # the example in problem.md
        (0, 600, "0/10 hours"),
        (0, 60, "0/1 hour"),
        (30, 45, "30/45 min"),  # a 45-minute goal stays in minutes
        (0, 45, "0/45 min"),
        (270, 600, "4h 30min / 10 hours"),
        (60, 45, "1 hour / 45min"),
        (150, 0, "2h 30min"),  # goal 0: just the amount
    ],
)
def test_format_done_vs_goal(done, goal, text):
    assert format_done_vs_goal(done, goal) == text


# --- Periods ---

@pytest.mark.parametrize(
    "period, moment, start",
    [
        ("day", "2026-11-18 15:30", "2026-11-18 00:00"),
        ("week", "2026-11-18 15:30", "2026-11-16 00:00"),  # Wednesday -> Monday
        ("week", "2026-11-16 00:00", "2026-11-16 00:00"),  # Monday midnight is the start
        ("week", "2026-11-22 23:59", "2026-11-16 00:00"),  # Sunday is still the same week
        ("month", "2026-11-18 15:30", "2026-11-01 00:00"),
        ("year", "2026-11-18 15:30", "2026-01-01 00:00"),
    ],
)
def test_period_start(period, moment, start):
    assert period_start(period, at(moment)) == at(start)


@pytest.mark.parametrize(
    "period, start, following",
    [
        ("day", "2026-12-31 00:00", "2027-01-01 00:00"),
        ("week", "2026-12-28 00:00", "2027-01-04 00:00"),
        ("month", "2026-11-01 00:00", "2026-12-01 00:00"),
        ("month", "2026-12-01 00:00", "2027-01-01 00:00"),  # December rolls into January
        ("year", "2026-01-01 00:00", "2027-01-01 00:00"),
    ],
)
def test_next_period_start(period, start, following):
    assert next_period_start(period, at(start)) == at(following)


@pytest.mark.parametrize(
    "period, start, before",
    [
        ("week", "2026-11-16 00:00", "2026-11-09 00:00"),
        ("month", "2026-03-01 00:00", "2026-02-01 00:00"),
        ("month", "2027-01-01 00:00", "2026-12-01 00:00"),
    ],
)
def test_previous_period_start(period, start, before):
    assert previous_period_start(period, at(start)) == at(before)


# --- Totals ---

def test_seconds_are_added_before_cutting_to_minutes():
    # Two 30-second sessions are 1 minute together, not 0 + 0.
    sessions = [
        Session(at("2026-11-16 10:00:00"), at("2026-11-16 10:00:30")),
        Session(at("2026-11-16 11:00:00"), at("2026-11-16 11:00:30")),
    ]
    assert minutes_between(sessions, at("2026-11-16 00:00"), at("2026-11-17 00:00"), now=at("2026-11-16 12:00")) == 1


def test_a_running_session_counts_up_to_now():
    sessions = [Session(at("2026-11-16 14:00"))]
    assert minutes_between(sessions, at("2026-11-16 00:00"), at("2026-11-17 00:00"), now=at("2026-11-16 14:25")) == 25


def test_a_session_counts_on_the_day_it_started_even_past_midnight():
    sessions = [session("2026-11-16 23:30", 60)]
    rows = day_rows(state(first_run=date(2026, 11, 16), sessions=sessions), now=at("2026-11-17 09:00"))
    assert [(row.day, row.minutes) for row in rows] == [(date(2026, 11, 17), 0), (date(2026, 11, 16), 60)]


@pytest.mark.parametrize("done, goal, percent", [(240, 600, 40), (600, 600, 100), (720, 600, 120), (1, 3, 33), (1, 2, 50), (1, 8, 13), (0, 0, None)])
def test_percent_rounds_to_nearest_with_half_up(done, goal, percent):
    assert percent_of(done, goal) == percent


# --- Progress (section 4) ---

def test_problem_md_example_4_of_10_hours_is_40_percent():
    s = state(sessions=[session("2026-11-16 09:00", 120), session("2026-11-17 18:00", 120)])
    p = progress(s, now=at("2026-11-18 12:00"))
    assert (p.label, p.done, p.goal, p.percent, p.extra) == ("This week", 240, 600, 40, 0)


def test_extra_hours_when_the_goal_is_passed():
    s = state(sessions=[session("2026-11-16 09:00", 660)])
    p = progress(s, now=at("2026-11-16 22:00"))
    assert (p.percent, p.extra) == (110, 60)


def test_a_new_week_starts_at_zero():
    s = state(sessions=[session("2026-11-17 09:00", 240)])
    p = progress(s, now=at("2026-11-23 08:00"))  # the next Monday
    assert (p.done, p.percent) == (0, 0)


def test_sessions_before_the_goal_was_set_dont_count():
    s = state(goal_set="2026-11-17 12:00", sessions=[session("2026-11-17 09:00", 60), session("2026-11-17 13:00", 30)])
    assert progress(s, now=at("2026-11-17 20:00")).done == 30


def test_reset_starts_progress_again_from_zero():
    s = state(sessions=[session("2026-11-16 09:00", 120), session("2026-11-17 15:00", 45)], reset="2026-11-17 12:00")
    assert progress(s, now=at("2026-11-17 20:00")).done == 45


def test_an_older_reset_than_the_goal_is_ignored():
    s = state(goal_set="2026-11-17 12:00", reset="2026-11-16 12:00", sessions=[session("2026-11-17 13:00", 30)])
    assert s.counting_from() == at("2026-11-17 12:00")


@pytest.mark.parametrize(
    "period, label, done",
    [("day", "Today", 30), ("month", "This month", 210), ("year", "This year", 270)],
)
def test_each_kind_of_period_counts_only_its_own_sessions(period, label, done):
    sessions = [
        session("2026-02-03 10:00", 60),  # earlier this year
        session("2026-11-02 10:00", 180),  # earlier this month
        session("2026-11-18 10:00", 30),  # today
    ]
    s = state(goal_minutes=60, period=period, goal_set="2026-01-01 00:00", sessions=sessions)
    p = progress(s, now=at("2026-11-18 20:00"))
    assert (p.label, p.done) == (label, done)


def test_goal_of_zero_has_no_percent():
    s = state(goal_minutes=0, sessions=[session("2026-11-16 09:00", 60)])
    p = progress(s, now=at("2026-11-16 12:00"))
    assert (p.percent, p.extra) == (None, 0)


# --- Past period (section 5) ---

def test_problem_md_example_past_week_4_of_10_hours():
    s = state(goal_set="2026-11-09 08:00", first_run=date(2026, 11, 9),
              sessions=[session("2026-11-10 09:00", 240)])
    assert past_period_text(s, now=at("2026-11-16 09:00")) == "past week = 4/10 hours"


def test_first_period_shows_zero():
    s = state(sessions=[session("2026-11-16 09:00", 120)])
    assert past_period_text(s, now=at("2026-11-17 09:00")) == "past week = 0/10 hours"


def test_past_day_with_a_45_minute_goal_stays_in_minutes():
    s = state(goal_minutes=45, period="day", goal_set="2026-11-15 08:00", first_run=date(2026, 11, 15),
              sessions=[session("2026-11-15 20:00", 30)])
    assert past_period_text(s, now=at("2026-11-16 09:00")) == "past day = 30/45 min"


def test_past_period_ignores_sessions_from_before_a_reset():
    s = state(goal_set="2026-11-09 08:00", first_run=date(2026, 11, 9), reset="2026-11-12 00:00",
              sessions=[session("2026-11-10 09:00", 240), session("2026-11-13 09:00", 60)])
    assert past_period_text(s, now=at("2026-11-16 09:00")) == "past week = 1/10 hours"


# --- The list of days (section 2) ---

def test_every_day_since_first_run_shows_newest_first_including_empty_days():
    s = state(first_run=date(2026, 11, 14), goal_set="2026-11-14 08:00",
              sessions=[session("2026-11-14 10:00", 90), session("2026-11-16 09:00", 30), session("2026-11-16 15:00", 45)])
    rows = day_rows(s, now=at("2026-11-16 20:00"))
    assert [(row.day.isoformat(), row.minutes) for row in rows] == [
        ("2026-11-16", 75), ("2026-11-15", 0), ("2026-11-14", 90),
    ]


def test_day_totals_keep_history_from_before_a_reset():
    s = state(sessions=[session("2026-11-16 09:00", 60)], reset="2026-11-16 12:00")
    assert day_rows(s, now=at("2026-11-16 20:00"))[0].minutes == 60


def test_daily_goal_marks_which_days_reached_it():
    s = state(goal_minutes=60, period="day", first_run=date(2026, 11, 15), goal_set="2026-11-15 00:00",
              sessions=[session("2026-11-15 10:00", 60), session("2026-11-16 10:00", 59)])
    assert [row.reached for row in day_rows(s, now=at("2026-11-16 20:00"))] == [False, True]


def test_goal_of_zero_means_every_day_is_reached():
    s = state(goal_minutes=0, period="day", first_run=date(2026, 11, 15), goal_set="2026-11-15 00:00")
    assert [row.reached for row in day_rows(s, now=at("2026-11-16 20:00"))] == [True, True]


def test_weekly_goal_does_not_mark_days():
    s = state(first_run=date(2026, 11, 16))
    assert day_rows(s, now=at("2026-11-16 20:00"))[0].reached is None


# --- The message at the top (bullet 7) ---

def test_top_message_easter_egg():
    assert top_message(state(goal_minutes=600)) == "time to work hard!!"
    assert top_message(state(goal_minutes=0)) == "have a great off day!!"
