"""Tests for the web app's buttons and pages (app.py), using Flask's test client.

The test client presses buttons without a browser. A fake clock decides what "now" is,
and every test saves to a temporary file, never the real data/tracker.json.
Only what each button does to the saved data, and the key text, is checked; the
layout and colours are not (the assignment says only the logic needs tests).
Nov 16, 2026 is a Monday.
"""

from datetime import datetime, timedelta

import pytest

import store
from app import create_app


class FakeClock:
    def __init__(self, text):
        self.moment = datetime.fromisoformat(text)

    def set(self, text):
        self.moment = datetime.fromisoformat(text)

    def __call__(self):
        return self.moment


@pytest.fixture
def clock():
    return FakeClock("2026-11-16 08:00")


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "data" / "tracker.json"


@pytest.fixture
def client(data_file, clock):
    return create_app(data_file=data_file, now=clock).test_client()


def page(client, url="/"):
    """The page's text after following any redirect."""
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def press(client, url, **form):
    """Press a button (send a form) and return the page it leads to."""
    return client.post(url, data=form, follow_redirects=True).get_data(as_text=True)


@pytest.fixture
def started(client):
    """A tracker set up with a 10-hour weekly goal at Mon Nov 16, 8:00 AM."""
    press(client, "/setup", hours="10", minutes="0", period="week")
    return client


# --- First run (spec 1) ---

def test_first_visit_asks_for_the_goal_and_saves_nothing_yet(client, data_file):
    text = page(client)
    assert "First, set your goal." in text
    assert not data_file.exists()


def test_setting_the_first_goal_saves_it(client, data_file):
    text = press(client, "/setup", hours="10", minutes="0", period="week")
    state = store.load(data_file)
    assert (state.goal.minutes, state.goal.period) == (600, "week")
    assert "time to work hard!!" in text
    assert "This week: 0min of 10 hours, 0% completed" in text


def test_a_goal_of_zero_shows_the_off_day_message(client):
    text = press(client, "/setup", hours="0", minutes="0", period="day")
    assert "have a great off day!!" in text
    assert "(no goal)" in text


def test_a_bad_first_goal_is_explained_and_not_saved(client, data_file):
    text = press(client, "/setup", hours="1", minutes="75", period="week")
    assert "Minutes must be from 0 to 59." in text
    assert not data_file.exists()


def test_the_first_goal_can_only_be_set_once(started, data_file):
    press(started, "/setup", hours="1", minutes="0", period="day")
    assert store.load(data_file).goal.minutes == 600


# --- The main page and day pages (spec 2, 3) ---

def test_days_with_no_hours_still_show_up(started, clock):
    clock.set("2026-11-18 09:00")
    text = page(started)
    for day in ("Wed Nov 18", "Tue Nov 17", "Mon Nov 16"):
        assert day in text
    assert text.index("Wed Nov 18") < text.index("Mon Nov 16")  # newest first


def test_adding_a_session_by_hand_shows_on_the_day_and_in_progress(started, clock, data_file):
    clock.set("2026-11-17 20:00")
    text = press(started, "/day/2026-11-16/sessions", start="14:05", hours="1", minutes="30")
    assert "Session added." in text
    assert "1 session, 1h 30min in total" in text
    assert "2:05 PM – 3:35 PM, 1h 30min" in text
    assert "This week: 1h 30min of 10 hours, 15% completed" in page(started)
    assert len(store.load(data_file).sessions) == 1


def test_a_bad_hand_added_session_is_explained_and_not_saved(started, clock, data_file):
    clock.set("2026-11-16 16:10")
    text = press(started, "/day/2026-11-16/sessions", start="16:00", hours="1", minutes="30")
    assert "A session can&#39;t end in the future." in text
    assert "Session added." not in text  # a refused session must not also say it was added
    assert store.load(data_file).sessions == []


def test_a_bad_new_goal_is_explained_and_not_announced_as_changed(started, data_file):
    text = press(started, "/goal", hours="x", minutes="0", period="day")
    assert "Hours and minutes must be whole numbers, like 1 and 30." in text
    assert "Goal changed." not in text
    assert store.load(data_file).goal.minutes == 600


def test_a_session_without_a_start_time_is_explained(started, data_file):
    text = press(started, "/day/2026-11-16/sessions", start="", hours="1", minutes="0")
    assert "Please pick the time the session started." in text
    assert store.load(data_file).sessions == []


@pytest.mark.parametrize("url", ["/day/2026-11-15", "/day/2026-11-17", "/day/not-a-date"])
def test_days_outside_the_list_are_not_found(started, url):
    # The list runs from the first run (Nov 16) to today (Nov 16 in this test).
    assert started.get(url).status_code == 404


def test_problem_md_example_past_week_and_40_percent(client, clock):
    press(client, "/setup", hours="10", minutes="0", period="week")
    clock.set("2026-11-20 20:00")
    press(client, "/day/2026-11-17/sessions", start="09:00", hours="4", minutes="0")
    assert "This week: 4 hours of 10 hours, 40% completed" in page(client)
    clock.set("2026-11-23 09:00")  # Monday comes
    assert "past week = 4/10 hours" in page(client)


def test_extra_hours_show_when_the_goal_is_passed(client, clock):
    press(client, "/setup", hours="1", minutes="0", period="day")
    clock.set("2026-11-16 20:00")
    text = press(client, "/day/2026-11-16/sessions", start="09:00", hours="1", minutes="45")
    text = page(client)
    assert "175% completed" in text
    assert "Extra hours: 45min" in text


# --- The clock (spec 3) ---

def keep_page_open(client, clock, start, minutes):
    """Act like an open browser tab: check in every 30 seconds for this many minutes."""
    begin = datetime.fromisoformat(start)
    for half_minutes in range(1, minutes * 2 + 1):
        clock.moment = begin + timedelta(seconds=30 * half_minutes)
        client.post("/clock/check-in")


def test_start_and_stop_the_clock(started, clock, data_file):
    clock.set("2026-11-16 14:00")
    text = press(started, "/clock/start")
    assert "Clock running since 2:00 PM" in text
    keep_page_open(started, clock, "2026-11-16 14:00", 90)  # now 3:30 PM
    text = press(started, "/clock/stop")
    assert "Session saved." in text
    assert "2:00 PM – 3:30 PM, 1h 30min" in text
    assert "Clock running" not in text


def test_stop_after_the_page_stopped_checking_in_explains_what_happened(started, clock, data_file):
    clock.set("2026-11-16 14:00")
    press(started, "/clock/start")
    keep_page_open(started, clock, "2026-11-16 14:00", 20)  # checks in until 2:20 PM
    clock.set("2026-11-16 16:00")  # the computer slept; Stop is pressed after waking up
    text = press(started, "/clock/stop")
    assert "The clock had already stopped at 2:20 PM" in text
    assert "2:00 PM – 2:20 PM, 20min" in text
    assert store.load(data_file).sessions[0].end == datetime(2026, 11, 16, 14, 20)


def test_starting_a_second_clock_is_explained(started, clock, data_file):
    press(started, "/clock/start")
    text = press(started, "/clock/start")
    assert "A clock is already running. Stop it first." in text
    assert len(store.load(data_file).sessions) == 1


def test_check_in_answers_whether_the_clock_runs(started, clock, data_file):
    assert started.post("/clock/check-in").get_json() == {"running": False}
    press(started, "/clock/start")
    clock.set("2026-11-16 08:00:30")
    assert started.post("/clock/check-in").get_json() == {"running": True}
    assert store.load(data_file).sessions[0].last_seen == datetime(2026, 11, 16, 8, 0, 30)


def test_a_closed_tab_ends_the_session_at_its_last_check_in(started, clock, data_file):
    clock.set("2026-11-16 14:00")
    press(started, "/clock/start")
    keep_page_open(started, clock, "2026-11-16 14:00", 20)  # checks in until 2:20 PM
    clock.set("2026-11-16 18:00")  # the tab was closed; this is the next page load
    text = page(started, "/day/2026-11-16")
    assert "2:00 PM – 2:20 PM, 20min" in text
    assert store.load(data_file).sessions[0].end == datetime(2026, 11, 16, 14, 20)


def test_stop_without_a_running_clock_is_explained(started):
    assert "No clock is running." in press(started, "/clock/stop")


def test_start_button_only_on_today_and_when_no_clock_runs(started, clock):
    clock.set("2026-11-17 10:00")
    assert "Start the clock" in page(started, "/day/2026-11-17")
    assert "Start the clock" not in page(started, "/day/2026-11-16")
    press(started, "/clock/start")
    assert "Start the clock" not in page(started, "/day/2026-11-17")


# --- Goal, reset and deadlines (spec 1, 6, 7) ---

def test_changing_the_goal_counts_from_zero(started, clock, data_file):
    clock.set("2026-11-16 12:00")
    press(started, "/day/2026-11-16/sessions", start="09:00", hours="2", minutes="0")
    clock.set("2026-11-16 13:00")
    text = press(started, "/goal", hours="0", minutes="45", period="day")
    assert "Goal changed. It counts from 0 starting now." in text
    assert "Today: 0min of 45min, 0% completed" in text
    assert "2 hours" in text  # the day keeps its history
    assert store.load(data_file).goal.minutes == 45


def test_reset_asks_first_and_keeps_the_days(started, clock, data_file):
    clock.set("2026-11-16 12:00")
    press(started, "/day/2026-11-16/sessions", start="09:00", hours="2", minutes="0")
    assert "Nothing was reset." in press(started, "/reset")  # not confirmed
    assert store.load(data_file).reset_at is None
    clock.set("2026-11-16 13:00")
    text = press(started, "/reset", sure="yes")
    assert "Progress counts from 0 starting now" in text
    assert "This week: 0min of 10 hours, 0% completed" in text
    assert len(store.load(data_file).sessions) == 1


def test_add_and_remove_deadlines(started, clock, data_file):
    press(started, "/deadlines", name="Essay", date="2026-11-21", time="09:00")
    text = press(started, "/deadlines", name="CSC 300 final", date="2026-11-20", time="")
    assert "CSC 300 final: 4 days left" in text
    assert "Essay: 5 days left" in text
    assert text.index("CSC 300 final") < text.index("Essay")  # soonest first
    clock.set("2026-11-24 12:00")
    assert "CSC 300 final: 3 days past deadline" in page(started)
    essay_index = [d.name for d in store.load(data_file).deadlines].index("Essay")
    press(started, f"/deadlines/{essay_index}/remove")
    assert [d.name for d in store.load(data_file).deadlines] == ["CSC 300 final"]


def test_a_deadline_without_a_name_or_date_is_explained(started, data_file):
    assert "Please give the deadline a name" in press(started, "/deadlines", name="", date="2026-11-20")
    assert "Please pick the deadline&#39;s date." in press(started, "/deadlines", name="Essay", date="")
    assert store.load(data_file).deadlines == []


# --- A damaged saved file (spec 9) ---

def test_a_damaged_file_shows_an_explanation_and_is_not_changed(client, data_file):
    data_file.parent.mkdir()
    data_file.write_text("{oops", encoding="utf-8")
    response = client.get("/")
    assert response.status_code == 500
    assert "is damaged and can&#39;t be read" in response.get_data(as_text=True)
    assert data_file.read_text(encoding="utf-8") == "{oops"


# --- Editing and deleting a session (later bullet 1, spec 3) ---

def add_two_sessions(client, clock):
    """Mon Nov 16: 9:00-10:00 AM and 1:00-1:30 PM, added at 10 PM."""
    clock.set("2026-11-16 22:00")
    press(client, "/day/2026-11-16/sessions", start="09:00", hours="1", minutes="0")
    press(client, "/day/2026-11-16/sessions", start="13:00", hours="0", minutes="30")


def test_later_bullet_1_edit_button_changes_the_saved_session(started, clock, data_file):
    add_two_sessions(started, clock)
    text = press(started, "/sessions/0/edit", was="2026-11-16T09:00:00", start="08:30", hours="2", minutes="0")
    assert "Session changed." in text
    assert "8:30 AM – 10:30 AM, 2 hours" in text
    assert "2 sessions, 2h 30min in total" in text
    saved = store.load(data_file).sessions[0]
    assert (saved.start, saved.end) == (datetime(2026, 11, 16, 8, 30), datetime(2026, 11, 16, 10, 30))
    assert "This week: 2h 30min of 10 hours, 25% completed" in page(started)


def test_later_bullet_1_an_edit_into_the_future_is_explained_and_not_saved(started, clock, data_file):
    add_two_sessions(started, clock)  # it is 10 PM
    text = press(started, "/sessions/0/edit", was="2026-11-16T09:00:00", start="23:00", hours="0", minutes="30")
    assert "A session can&#39;t end in the future. It would end at 11:30 PM, but it&#39;s 10:00 PM now." in text
    assert "Session changed." not in text
    assert store.load(data_file).sessions[0].start == datetime(2026, 11, 16, 9, 0)


def test_later_bullet_1_adding_a_session_in_the_future_is_still_refused(started, clock, data_file):
    clock.set("2026-11-16 22:00")
    text = press(started, "/day/2026-11-16/sessions", start="23:00", hours="0", minutes="30")
    assert "A session can&#39;t end in the future." in text
    assert store.load(data_file).sessions == []


def test_later_bullet_1_delete_asks_first_then_removes_only_that_session(started, clock, data_file):
    add_two_sessions(started, clock)
    assert "Nothing was deleted." in press(started, "/sessions/0/delete", was="2026-11-16T09:00:00")
    assert len(store.load(data_file).sessions) == 2
    text = press(started, "/sessions/0/delete", was="2026-11-16T09:00:00", sure="yes")
    assert "Session deleted." in text
    assert "1 session, 30min in total" in text
    assert [s.start for s in store.load(data_file).sessions] == [datetime(2026, 11, 16, 13, 0)]


def test_later_bullet_1_deleting_the_running_session_stops_the_clock(started, clock, data_file):
    clock.set("2026-11-16 14:00")
    press(started, "/clock/start")
    clock.set("2026-11-16 14:00:20")
    text = press(started, "/sessions/0/delete", was="2026-11-16T14:00:00", sure="yes")
    assert "Session deleted." in text
    assert "Clock running" not in text
    assert store.load(data_file).sessions == []


def test_later_bullet_1_the_running_session_has_no_edit_form(started, clock):
    clock.set("2026-11-16 14:00")
    press(started, "/clock/start")
    text = page(started, "/day/2026-11-16")
    assert "Press Stop before editing." in text
    assert "/sessions/0/edit" not in text
    assert "/sessions/0/delete" in text


def test_later_bullet_1_a_session_already_deleted_in_another_tab_is_explained(started, clock, data_file):
    add_two_sessions(started, clock)
    press(started, "/sessions/0/delete", was="2026-11-16T09:00:00", sure="yes")
    # The other tab still shows the old list, where 1:00 PM was session 1.
    text = press(started, "/sessions/0/edit", was="2026-11-16T09:00:00", start="09:00", hours="3", minutes="0")
    assert "That session was already changed or deleted. Nothing was changed." in text
    saved = store.load(data_file).sessions
    assert [(s.start, s.end) for s in saved] == [(datetime(2026, 11, 16, 13, 0), datetime(2026, 11, 16, 13, 30))]


def test_later_bullet_1_a_broken_was_field_is_a_bad_request(started, clock, data_file):
    add_two_sessions(started, clock)
    assert started.post("/sessions/0/delete", data={"was": "nonsense", "sure": "yes"}).status_code == 400
    assert len(store.load(data_file).sessions) == 2


# --- Streaks (later bullet 2, spec 4 Streaks) ---

def study_days(client, clock, first, last):
    """Add a 1-hour session at 9 AM on days first to last, counting Mon Nov 16 as day 1."""
    for n in range(first - 1, last):
        day = datetime(2026, 11, 16) + timedelta(days=n)
        clock.set(f"{day:%Y-%m-%d} 22:00")
        press(client, f"/day/{day:%Y-%m-%d}/sessions", start="09:00", hours="1", minutes="0")


@pytest.fixture
def daily(client):
    """A tracker set up with a 1-hour daily goal at Mon Nov 16, 8:00 AM."""
    press(client, "/setup", hours="1", minutes="0", period="day")
    return client


def test_later_bullet_2_main_page_shows_the_streak_message_after_5_days(daily, clock):
    study_days(daily, clock, 1, 4)
    assert "in a row" not in page(daily)
    study_days(daily, clock, 5, 5)
    assert "You&#39;ve hit your goal 5 days in a row. Keep it going!!" in page(daily)


def test_later_bullet_2_message_goes_away_after_a_missed_day(daily, clock):
    study_days(daily, clock, 1, 5)
    clock.set("2026-11-22 10:00")  # Sunday: Saturday was missed
    assert "in a row" not in page(daily)


def test_later_bullet_2_reset_saves_the_best_streak(daily, clock, data_file):
    study_days(daily, clock, 1, 6)
    press(daily, "/reset", sure="yes")
    assert store.load(data_file).best_streak == 6
    assert "in a row" not in page(daily)


def test_later_bullet_2_changing_the_goal_saves_the_best_streak(daily, clock, data_file):
    study_days(daily, clock, 1, 3)
    press(daily, "/goal", hours="2", minutes="0", period="day")
    assert store.load(data_file).best_streak == 3


def test_later_bullet_2_a_bad_goal_change_saves_no_best_streak(daily, clock, data_file):
    study_days(daily, clock, 1, 3)
    press(daily, "/goal", hours="2", minutes="0", period="fortnight")
    assert store.load(data_file).best_streak == 0
