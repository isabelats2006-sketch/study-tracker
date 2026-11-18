"""Tests for saving and loading (spec.md section 9).

Every test uses tmp_path, an empty folder pytest makes for it, never the real data/ folder.
"""

import json
from datetime import date, datetime, time

import pytest

from store import StoreProblem, load, save
from tracker import add_deadline, add_manual_session, new_state, reset, start_clock


def at(text):
    return datetime.fromisoformat(text)


def full_state():
    """A state with a bit of everything in it."""
    s = new_state(45, "day", at("2026-11-16 08:00"))
    add_manual_session(s, date(2026, 11, 16), time(9, 0), 90, now=at("2026-11-16 12:00"))
    reset(s, at("2026-11-16 12:30"))
    add_deadline(s, "CSC 300 final", date(2026, 11, 20))
    add_deadline(s, "Essay", date(2026, 11, 21), time(9, 15))
    start_clock(s, at("2026-11-16 14:00:07"))  # still running, seconds included
    return s


def test_save_then_load_gives_back_the_same_state(tmp_path):
    path = tmp_path / "data" / "tracker.json"
    state = full_state()
    save(path, state)
    assert load(path) == state


def test_save_makes_the_data_folder(tmp_path):
    path = tmp_path / "data" / "tracker.json"
    save(path, full_state())
    assert path.is_file()


def test_nothing_saved_yet_means_first_run(tmp_path):
    assert load(tmp_path / "data" / "tracker.json") is None


def test_saved_file_is_readable_json_with_local_times(tmp_path):
    path = tmp_path / "tracker.json"
    save(path, full_state())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["goal"] == {"minutes": 45, "period": "day", "set_at": "2026-11-16T08:00:00"}
    assert data["sessions"][1] == {"start": "2026-11-16T14:00:07", "end": None, "last_seen": "2026-11-16T14:00:07"}


def test_saving_again_replaces_the_file_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "tracker.json"
    save(path, full_state())
    changed = full_state()
    changed.goal.minutes = 120
    save(path, changed)
    assert load(path).goal.minutes == 120
    assert [p.name for p in tmp_path.iterdir()] == ["tracker.json"]


def test_a_failed_save_leaves_the_old_file_untouched(tmp_path):
    path = tmp_path / "tracker.json"
    save(path, full_state())
    before = path.read_text(encoding="utf-8")
    broken = full_state()
    broken.goal.minutes = object()  # JSON can't hold this, so saving fails
    with pytest.raises(TypeError):
        save(path, broken)
    assert path.read_text(encoding="utf-8") == before
    assert [p.name for p in tmp_path.iterdir()] == ["tracker.json"]


@pytest.mark.parametrize(
    "text, kind",
    [
        ("{not json", "JSONDecodeError"),
        ('{"version": 1}', "KeyError"),
        ('{"version": 99}', "ValueError"),
        ("[]", "AttributeError"),
        ('{"version": 1, "first_run": "yesterday", "goal": {"minutes": 1, "period": "day", "set_at": null},'
         ' "reset_at": null, "sessions": [], "deadlines": []}', "ValueError"),
    ],
)
def test_a_damaged_file_is_explained_and_not_changed(tmp_path, text, kind):
    path = tmp_path / "tracker.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(StoreProblem) as caught:
        load(path)
    assert str(caught.value) == (
        f"The saved file {path} is damaged and can't be read ({kind}). "
        "Nothing was changed. Fix the file, or move it somewhere else to start fresh."
    )
    assert path.read_text(encoding="utf-8") == text


def test_later_bullet_2_best_streak_is_saved_and_loaded(tmp_path):
    path = tmp_path / "tracker.json"
    state = full_state()
    state.best_streak = 7
    save(path, state)
    assert json.loads(path.read_text(encoding="utf-8"))["best_streak"] == 7
    assert load(path).best_streak == 7


def test_later_bullet_2_a_file_from_before_streaks_loads_with_best_streak_0(tmp_path):
    path = tmp_path / "tracker.json"
    save(path, full_state())
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["best_streak"]  # how files looked before later bullet 2
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load(path).best_streak == 0
