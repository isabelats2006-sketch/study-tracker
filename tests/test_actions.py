"""Tests for the goal form, reset, hand-added sessions, the clock and deadlines
(spec.md sections 1, 3, 6, 7). Nov 16, 2026 is a Monday.
"""

from datetime import date, datetime, time, timedelta

import pytest

from tracker import (
    GONE_AFTER_SECONDS, Deadline, TrackerProblem, add_deadline, add_manual_session, check_in,
    close_abandoned, deadline_text, deadlines_in_order, format_clock, new_state, parse_amount,
    progress, remove_deadline, reset, running_session, set_goal, start_clock, stop_clock,
)


def at(text):
    return datetime.fromisoformat(text)


def fresh(now="2026-11-16 08:00", minutes=600, period="week"):
    return new_state(minutes, period, at(now))


def problem(action):
    """The message of the TrackerProblem that action() raises."""
    with pytest.raises(TrackerProblem) as caught:
        action()
    return str(caught.value)


# --- Amounts typed in a form ---

@pytest.mark.parametrize(
    "hours, minutes, total",
    [("10", "0", 600), ("0", "45", 45), ("1", "30", 90), ("", "45", 45), (" 2 ", "", 120), ("", "", 0)],
)
def test_parse_amount(hours, minutes, total):
    assert parse_amount(hours, minutes) == total


@pytest.mark.parametrize(
    "hours, minutes, message",
    [
        ("1.5", "0", "Hours and minutes must be whole numbers, like 1 and 30."),
        ("one", "0", "Hours and minutes must be whole numbers, like 1 and 30."),
        ("-1", "0", "Hours and minutes can't be negative."),
        ("1", "60", "Minutes must be from 0 to 59."),
    ],
)
def test_parse_amount_explains_bad_input(hours, minutes, message):
    assert problem(lambda: parse_amount(hours, minutes)) == message


# --- First run, changing the goal, reset (sections 1 and 7) ---

def test_first_run_sets_the_goal_and_the_first_day():
    s = fresh("2026-11-16 08:00", 45, "day")
    assert (s.first_run, s.goal.minutes, s.goal.period, s.goal.set_at) == (date(2026, 11, 16), 45, "day", at("2026-11-16 08:00"))


def test_a_goal_of_zero_is_allowed():
    assert fresh(minutes=0).goal.minutes == 0


def test_period_must_be_one_of_the_four():
    assert problem(lambda: new_state(60, "hourly", at("2026-11-16 08:00"))) == (
        "Please choose Daily, Weekly, Monthly or Yearly."
    )


def test_a_new_goal_counts_from_zero_but_keeps_sessions():
    s = fresh()
    add_manual_session(s, date(2026, 11, 16), time(9, 0), 120, now=at("2026-11-16 12:00"))
    set_goal(s, 120, "day", at("2026-11-16 13:00"))
    assert progress(s, at("2026-11-16 14:00")).done == 0
    assert len(s.sessions) == 1


def test_reset_keeps_everything_and_counts_from_now():
    s = fresh()
    add_manual_session(s, date(2026, 11, 16), time(9, 0), 120, now=at("2026-11-16 12:00"))
    reset(s, at("2026-11-16 13:00"))
    assert s.reset_at == at("2026-11-16 13:00")
    assert len(s.sessions) == 1
    assert progress(s, at("2026-11-16 14:00")).done == 0


# --- Adding a session by hand (section 3) ---

def test_a_session_can_be_added_by_hand_on_a_past_day():
    s = fresh("2026-11-16 08:00")
    session = add_manual_session(s, date(2026, 11, 17), time(14, 5), 90, now=at("2026-11-19 10:00"))
    assert (session.start, session.end) == (at("2026-11-17 14:05"), at("2026-11-17 15:35"))
    assert s.sessions == [session]


def test_a_session_ending_exactly_now_is_allowed():
    s = fresh()
    add_manual_session(s, date(2026, 11, 16), time(9, 0), 60, now=at("2026-11-16 10:00"))
    assert len(s.sessions) == 1


@pytest.mark.parametrize(
    "day, start, minutes, message",
    [
        (date(2026, 11, 16), time(9, 0), 0, "A session must be at least 1 minute long."),
        (date(2026, 11, 16), time(9, 0), 24 * 60 + 1, "A session can't be longer than 24 hours."),
        (date(2026, 11, 15), time(9, 0), 30, "That day is before you started using the tracker (Nov 16)."),
        (date(2026, 11, 16), time(16, 0), 90,
         "A session can't end in the future. It would end at 5:30 PM, but it's 4:10 PM now."),
        (date(2026, 11, 16), time(23, 0), 120,
         "A session can't end in the future. It would end at 1:00 AM on Nov 17, but it's 4:10 PM now."),
    ],
)
def test_hand_added_sessions_that_break_a_rule_are_explained_and_not_added(day, start, minutes, message):
    s = fresh("2026-11-16 08:00")
    assert problem(lambda: add_manual_session(s, day, start, minutes, now=at("2026-11-16 16:10"))) == message
    assert s.sessions == []


@pytest.mark.parametrize(
    "clock, text",
    [("00:05", "12:05 AM"), ("09:30", "9:30 AM"), ("12:00", "12:00 PM"), ("14:05", "2:05 PM"), ("23:59", "11:59 PM")],
)
def test_format_clock(clock, text):
    assert format_clock(at(f"2026-11-16 {clock}")) == text


# --- The clock (section 3) ---

def test_start_then_stop_makes_a_session():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00"))
    stop_clock(s, at("2026-11-16 15:30"))
    assert (s.sessions[0].start, s.sessions[0].end) == (at("2026-11-16 14:00"), at("2026-11-16 15:30"))
    assert running_session(s) is None


def test_only_one_clock_can_run():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00"))
    assert problem(lambda: start_clock(s, at("2026-11-16 14:05"))) == "A clock is already running. Stop it first."
    assert len(s.sessions) == 1


def test_stop_without_a_running_clock_is_explained():
    assert problem(lambda: stop_clock(fresh(), at("2026-11-16 14:00"))) == "No clock is running."


def test_check_in_keeps_a_running_clock_alive():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00:00"))
    for seconds in range(30, 3601, 30):  # an hour of check-ins every 30 seconds
        now = at("2026-11-16 14:00:00") + timedelta(seconds=seconds)
        assert close_abandoned(s, now) is False
        assert check_in(s, now) is True
    assert running_session(s) is not None


def test_closed_tab_ends_the_session_at_its_last_check_in():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00:00"))
    check_in(s, at("2026-11-16 14:20:00"))
    # The tab is closed. The next page load is the next morning.
    assert close_abandoned(s, at("2026-11-17 09:00")) is True
    assert s.sessions[0].end == at("2026-11-16 14:20:00")
    assert running_session(s) is None


def test_exactly_90_seconds_without_check_in_is_still_running():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00:00"))
    check_in(s, at("2026-11-16 14:10:00"))
    later = at("2026-11-16 14:10:00") + timedelta(seconds=GONE_AFTER_SECONDS)
    assert close_abandoned(s, later) is False
    assert close_abandoned(s, later + timedelta(seconds=1)) is True


def test_tab_closed_before_its_first_check_in_leaves_no_empty_session():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00:00"))
    assert close_abandoned(s, at("2026-11-16 15:00")) is True
    assert s.sessions == []


def test_check_in_without_a_running_clock_returns_false():
    assert check_in(fresh(), at("2026-11-16 14:00")) is False


def test_a_running_clock_counts_in_progress_before_it_stops():
    s = fresh()
    start_clock(s, at("2026-11-16 14:00"))
    assert progress(s, at("2026-11-16 14:45")).done == 45


# --- Deadlines (section 6) ---

def test_deadline_without_a_time_means_11_59_pm():
    s = fresh()
    deadline = add_deadline(s, "  CSC 300 final ", date(2026, 11, 20))
    assert deadline == Deadline("CSC 300 final", at("2026-11-20 23:59"))


def test_deadline_with_a_time():
    assert add_deadline(fresh(), "Essay", date(2026, 11, 21), time(9, 0)).due == at("2026-11-21 09:00")


@pytest.mark.parametrize(
    "name, message",
    [("", "Please give the deadline a name, like CSC 300 final."),
     ("   ", "Please give the deadline a name, like CSC 300 final."),
     ("x" * 61, "Please keep the deadline name to 60 characters or less.")],
)
def test_deadline_name_rules(name, message):
    s = fresh()
    assert problem(lambda: add_deadline(s, name, date(2026, 11, 20))) == message
    assert s.deadlines == []


@pytest.mark.parametrize(
    "now, text",
    [
        ("2026-11-15 10:00", "CSC 300 final: 5 days left"),
        ("2026-11-19 23:00", "CSC 300 final: 1 day left"),
        ("2026-11-20 00:01", "CSC 300 final: today"),
        ("2026-11-20 23:59", "CSC 300 final: today"),
        ("2026-11-20 23:59:30", "CSC 300 final: less than 1 minute past deadline"),
        ("2026-11-21 00:00", "CSC 300 final: 1 minute past deadline"),
        ("2026-11-21 00:01", "CSC 300 final: 2 minutes past deadline"),
        ("2026-11-21 00:59", "CSC 300 final: 1 hour past deadline"),
        ("2026-11-21 05:30", "CSC 300 final: 5 hours past deadline"),
        ("2026-11-21 23:59", "CSC 300 final: 1 day past deadline"),
        ("2026-11-24 12:00", "CSC 300 final: 3 days past deadline"),
    ],
)
def test_deadline_countdown_and_past_deadline(now, text):
    deadline = Deadline("CSC 300 final", at("2026-11-20 23:59"))
    assert deadline_text(deadline, at(now)) == text


def test_deadlines_are_shown_soonest_first_and_removed_only_by_the_user():
    s = fresh()
    add_deadline(s, "Essay", date(2026, 11, 21))
    add_deadline(s, "CSC 300 final", date(2026, 11, 20))
    assert [d.name for _, d in deadlines_in_order(s)] == ["CSC 300 final", "Essay"]
    index_of_essay = deadlines_in_order(s)[1][0]
    remove_deadline(s, index_of_essay)
    assert [d.name for d in s.deadlines] == ["CSC 300 final"]


def test_removing_a_deadline_that_is_gone_is_explained():
    assert problem(lambda: remove_deadline(fresh(), 0)) == "That deadline doesn't exist anymore."
