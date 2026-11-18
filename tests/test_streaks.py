"""Tests for goal streaks and the streak message (later bullet 2, spec.md section 4, Streaks).

Later bullet 2: the program remembers streaks, and after the longest amount of days in a
row it says "You've hit your goal 5 days in a row. Keep it going!!". The first message
ever comes after 5 days. Nov 16, 2026 is a Monday.
"""

from datetime import date, datetime, time, timedelta

from tracker import (
    Goal, add_manual_session, best_streak_before, current_streak, daily_share, delete_session,
    new_state, reset, set_goal, start_clock, streak_message,
)

MON = date(2026, 11, 16)


def at(text):
    return datetime.fromisoformat(text)


def day(n):
    """Day n of the test, counting MON as day 1."""
    return MON + timedelta(days=n - 1)


def evening(n):
    """10 PM on day n: late enough that every test session has already ended."""
    d = day(n)
    return datetime(d.year, d.month, d.day, 22, 0)


def study(state, days, minutes=60):
    """A session at 9 AM, `minutes` long, on each of the given day numbers."""
    for n in days:
        add_manual_session(state, day(n), time(9, 0), minutes, now=evening(n))


def daily_goal():
    """A 1-hour daily goal set at 8 AM on day 1."""
    return new_state(60, "day", at("2026-11-16 08:00"))


def message(n):
    return f"You've hit your goal {n} days in a row. Keep it going!!"


# --- What counts as hitting the goal on a day ---

def test_later_bullet_2_daily_share_is_the_whole_daily_goal():
    assert daily_share(Goal(60, "day", at("2026-11-16 08:00")), MON) == 60


def test_later_bullet_2_daily_share_of_a_weekly_goal_is_rounded_up():
    # 10 hours / 7 days = 85.7 minutes, so a day needs 86
    assert daily_share(Goal(600, "week", at("2026-11-16 08:00")), MON) == 86


def test_later_bullet_2_daily_share_of_a_monthly_goal_uses_that_months_days():
    goal = Goal(30 * 60, "month", at("2026-11-01 08:00"))
    assert daily_share(goal, date(2026, 11, 5)) == 60  # November: 30 days
    assert daily_share(goal, date(2026, 12, 5)) == 59  # December: 31 days, 58.06 -> 59
    assert daily_share(goal, date(2027, 2, 5)) == 65  # February 2027: 28 days, 64.3 -> 65


def test_later_bullet_2_daily_share_of_a_yearly_goal_knows_leap_years():
    goal = Goal(365 * 60, "year", at("2026-01-01 08:00"))
    assert daily_share(goal, date(2026, 6, 1)) == 60  # 365 days
    assert daily_share(goal, date(2028, 6, 1)) == 60  # 366 days: 59.8 -> 60
    assert daily_share(Goal(366, "year", at("2026-01-01 08:00")), date(2028, 6, 1)) == 1
    assert daily_share(Goal(366, "year", at("2026-01-01 08:00")), date(2026, 6, 1)) == 2


def test_later_bullet_2_a_day_just_under_the_goal_does_not_count():
    state = daily_goal()
    study(state, [1, 2, 3, 4], 60)
    study(state, [5], 59)
    assert current_streak(state, evening(5)) == 4  # day 5 is today: not hit yet
    assert current_streak(state, evening(6)) == 0  # day 5 was missed


def test_later_bullet_2_weekly_goal_needs_the_daily_share_each_day():
    state = new_state(600, "week", at("2026-11-16 08:00"))
    study(state, [1, 2, 3, 4, 5], 86)
    assert streak_message(state, evening(5)) == message(5)

    short = new_state(600, "week", at("2026-11-16 08:00"))
    study(short, [1, 2, 3, 4], 86)
    study(short, [5], 85)
    assert current_streak(short, evening(5)) == 4
    assert streak_message(short, evening(5)) is None


# --- The current streak ---

def test_later_bullet_2_streak_counts_days_in_a_row():
    state = daily_goal()
    study(state, [1, 2, 3])
    assert current_streak(state, evening(3)) == 3


def test_later_bullet_2_today_not_hit_yet_does_not_break_the_streak():
    state = daily_goal()
    study(state, [1, 2, 3, 4, 5])
    assert current_streak(state, at("2026-11-21 09:00")) == 5  # day 6, nothing studied yet
    assert streak_message(state, at("2026-11-21 23:59")) == message(5)


def test_later_bullet_2_today_counts_as_soon_as_it_hits_the_goal():
    state = daily_goal()
    study(state, [1, 2, 3, 4])
    add_manual_session(state, day(5), time(9, 0), 60, now=at("2026-11-20 10:00"))
    assert current_streak(state, at("2026-11-20 10:00")) == 5


def test_later_bullet_2_a_running_clock_counts_toward_today():
    state = daily_goal()
    study(state, [1, 2, 3, 4])
    start_clock(state, at("2026-11-20 09:00"))
    assert current_streak(state, at("2026-11-20 09:59")) == 4
    assert current_streak(state, at("2026-11-20 10:00")) == 5


def test_later_bullet_2_a_missed_day_puts_the_streak_back_to_0():
    state = daily_goal()
    study(state, [1, 2, 3, 4, 5])
    assert current_streak(state, evening(7)) == 0  # day 6 was missed
    assert streak_message(state, evening(7)) is None


# --- The message ---

def test_later_bullet_2_first_message_ever_is_after_5_days():
    state = daily_goal()
    study(state, [1, 2, 3, 4])
    assert streak_message(state, evening(4)) is None
    study(state, [5])
    assert streak_message(state, evening(5)) == message(5)


def test_later_bullet_2_message_keeps_showing_while_the_record_goes_on():
    state = daily_goal()
    study(state, [1, 2, 3, 4, 5, 6])
    assert streak_message(state, evening(6)) == message(6)


def test_later_bullet_2_a_short_earlier_streak_still_needs_5_days():
    state = daily_goal()
    study(state, [1, 2, 3])  # a 3-day streak, then day 4 missed
    study(state, [5, 6, 7, 8])
    assert streak_message(state, evening(8)) is None
    study(state, [9])
    assert streak_message(state, evening(9)) == message(5)


def test_later_bullet_2_a_new_streak_must_beat_the_longest_one():
    state = daily_goal()
    study(state, range(1, 8))  # 7 days, then day 8 missed
    study(state, range(9, 16))  # 7 days again: only a tie
    assert best_streak_before(state, evening(15)) == 7
    assert streak_message(state, evening(15)) is None
    study(state, [16])
    assert streak_message(state, evening(16)) == message(8)


def test_later_bullet_2_no_streaks_with_a_goal_of_0():
    state = new_state(0, "day", at("2026-11-16 08:00"))
    study(state, [1, 2, 3, 4, 5])
    assert current_streak(state, evening(5)) == 0
    assert streak_message(state, evening(5)) is None
    assert current_streak(new_state(0, "day", at("2026-11-16 08:00")), evening(6)) == 0


def test_later_bullet_2_deleting_a_session_updates_the_streak():
    state = daily_goal()
    study(state, [1, 2, 3, 4, 5])
    delete_session(state, 2, at("2026-11-18 09:00"))  # day 3's session
    assert current_streak(state, evening(5)) == 2
    assert streak_message(state, evening(5)) is None


# --- Goal changes and Reset ---

def test_later_bullet_2_changing_the_goal_starts_a_new_streak_and_keeps_the_best():
    state = daily_goal()
    study(state, range(1, 7))  # 6 days
    set_goal(state, 60, "day", at("2026-11-22 08:00"))  # day 7, before studying
    assert state.best_streak == 6
    assert current_streak(state, at("2026-11-22 08:00")) == 0
    study(state, range(7, 13))  # 6 more days: a tie with the saved best
    assert current_streak(state, evening(12)) == 6
    assert streak_message(state, evening(12)) is None
    study(state, [13])
    assert streak_message(state, evening(13)) == message(7)


def test_later_bullet_2_reset_starts_a_new_streak_and_keeps_the_best():
    state = daily_goal()
    study(state, range(1, 6))  # 5 days
    reset(state, at("2026-11-20 23:00"))  # late on day 5
    assert state.best_streak == 5
    assert current_streak(state, at("2026-11-20 23:00")) == 0
    assert streak_message(state, at("2026-11-20 23:00")) is None


def test_later_bullet_2_the_day_of_a_reset_counts_only_sessions_after_it():
    state = daily_goal()
    add_manual_session(state, MON, time(9, 0), 60, now=at("2026-11-16 12:00"))
    reset(state, at("2026-11-16 12:00"))
    assert current_streak(state, at("2026-11-16 12:00")) == 0
    add_manual_session(state, MON, time(13, 0), 60, now=at("2026-11-16 15:00"))
    assert current_streak(state, at("2026-11-16 15:00")) == 1


def test_later_bullet_2_saved_best_only_grows():
    state = daily_goal()
    study(state, range(1, 8))  # 7 days
    reset(state, evening(7))
    study(state, [8, 9])
    reset(state, evening(9))
    assert state.best_streak == 7
