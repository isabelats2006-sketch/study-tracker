"""Tests for editing and deleting a session (later bullet 1, spec.md section 3).

Later bullet 1: a session can be edited or deleted, and a session can't be in the future.
Nov 16, 2026 is a Monday.
"""

from datetime import date, datetime, time

import pytest

from tracker import (
    TrackerProblem, add_manual_session, day_rows, delete_session, edit_session, new_state,
    progress, reset, running_session, start_clock, stop_clock,
)

MON = date(2026, 11, 16)


def at(text):
    return datetime.fromisoformat(text)


def problem(action):
    """The message of the TrackerProblem that action() raises."""
    with pytest.raises(TrackerProblem) as caught:
        action()
    return str(caught.value)


@pytest.fixture
def state():
    """A 10-hour weekly goal set Mon 8:00 AM, with one session Mon 9:00-10:00 AM."""
    s = new_state(600, "week", at("2026-11-16 08:00"))
    add_manual_session(s, MON, time(9, 0), 60, now=at("2026-11-16 12:00"))
    return s


NINE = at("2026-11-16 09:00")  # the start the page saw for session 0


# --- Editing (later bullet 1) ---

def test_later_bullet_1_edit_changes_start_and_length(state):
    edit_session(state, 0, NINE, time(13, 15), 90, now=at("2026-11-16 22:00"))
    session = state.sessions[0]
    assert (session.start, session.end) == (at("2026-11-16 13:15"), at("2026-11-16 14:45"))
    assert len(state.sessions) == 1


def test_later_bullet_1_edit_keeps_the_session_on_its_day(state):
    edit_session(state, 0, NINE, time(7, 0), 30, now=at("2026-11-18 10:00"))  # edited on Wed
    assert state.sessions[0].start.date() == MON


def test_later_bullet_1_totals_and_progress_follow_the_edit(state):
    edit_session(state, 0, NINE, time(9, 0), 240, now=at("2026-11-16 22:00"))
    assert progress(state, at("2026-11-16 22:00")).done == 240
    assert day_rows(state, at("2026-11-16 22:00"))[0].minutes == 240


def test_later_bullet_1_moving_a_start_before_a_reset_takes_it_out_of_progress(state):
    reset(state, at("2026-11-16 12:00"))
    add_manual_session(state, MON, time(13, 0), 60, now=at("2026-11-16 15:00"))
    assert progress(state, at("2026-11-16 15:00")).done == 60
    edit_session(state, 1, at("2026-11-16 13:00"), time(11, 0), 60, now=at("2026-11-16 15:00"))
    assert progress(state, at("2026-11-16 15:00")).done == 0


@pytest.mark.parametrize(
    "start, minutes, message",
    [
        # The example in later bullet 1: at 10 PM a session can't start at 11 PM.
        (time(23, 0), 30,
         "A session can't end in the future. It would end at 11:30 PM, but it's 10:00 PM now."),
        # Starting in the past but running past now counts as the future too (decision 15).
        (time(21, 30), 60,
         "A session can't end in the future. It would end at 10:30 PM, but it's 10:00 PM now."),
        (time(9, 0), 0, "A session must be at least 1 minute long."),
        (time(9, 0), 24 * 60 + 1, "A session can't be longer than 24 hours."),
    ],
)
def test_later_bullet_1_an_edit_that_breaks_a_rule_is_explained_and_changes_nothing(state, start, minutes, message):
    assert problem(lambda: edit_session(state, 0, NINE, start, minutes, now=at("2026-11-16 22:00"))) == message
    session = state.sessions[0]
    assert (session.start, session.end) == (NINE, at("2026-11-16 10:00"))


def test_later_bullet_1_an_edit_ending_exactly_now_is_allowed(state):
    edit_session(state, 0, NINE, time(21, 0), 60, now=at("2026-11-16 22:00"))
    assert state.sessions[0].end == at("2026-11-16 22:00")


def test_later_bullet_1_adding_in_the_future_is_still_refused(state):
    # The 10 PM / 11 PM example from later bullet 1, for adding.
    assert problem(lambda: add_manual_session(state, MON, time(23, 0), 30, now=at("2026-11-16 22:00"))) == (
        "A session can't end in the future. It would end at 11:30 PM, but it's 10:00 PM now."
    )
    assert len(state.sessions) == 1


def test_later_bullet_1_a_running_session_cant_be_edited(state):
    start_clock(state, at("2026-11-16 14:00"))
    running = state.sessions[1]
    assert problem(lambda: edit_session(state, 1, running.start, time(13, 0), 30, now=at("2026-11-16 14:30"))) == (
        "This session's clock is still running. Press Stop before editing it."
    )
    assert (running.start, running.end) == (at("2026-11-16 14:00"), None)


def test_later_bullet_1_a_stopped_clock_session_can_be_edited(state):
    start_clock(state, at("2026-11-16 14:00"))
    stop_clock(state, at("2026-11-16 15:00"))
    edit_session(state, 1, at("2026-11-16 14:00"), time(14, 0), 45, now=at("2026-11-16 16:00"))
    assert state.sessions[1].end == at("2026-11-16 14:45")


# --- Deleting (later bullet 1) ---

def test_later_bullet_1_delete_removes_only_that_session(state):
    add_manual_session(state, MON, time(13, 0), 30, now=at("2026-11-16 15:00"))
    delete_session(state, 0, NINE)
    assert [s.start for s in state.sessions] == [at("2026-11-16 13:00")]
    assert progress(state, at("2026-11-16 15:00")).done == 30


def test_later_bullet_1_deleting_a_running_session_cancels_the_clock(state):
    start_clock(state, at("2026-11-16 14:00"))
    delete_session(state, 1, at("2026-11-16 14:00"))
    assert running_session(state) is None
    assert len(state.sessions) == 1


# --- A session already changed or deleted elsewhere (spec 3) ---

@pytest.mark.parametrize("index, was_start", [(5, NINE), (-1, NINE), (0, at("2026-11-16 09:01"))])
def test_later_bullet_1_a_session_that_moved_or_is_gone_is_not_touched(state, index, was_start):
    message = "That session was already changed or deleted. Nothing was changed."
    assert problem(lambda: edit_session(state, index, was_start, time(8, 0), 30, now=at("2026-11-16 22:00"))) == message
    assert problem(lambda: delete_session(state, index, was_start)) == message
    assert (state.sessions[0].start, state.sessions[0].end) == (NINE, at("2026-11-16 10:00"))
