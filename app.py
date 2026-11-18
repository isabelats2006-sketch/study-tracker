"""Study tracker: the web app (spec.md). Run it with:  python app.py

Then open http://127.0.0.1:5000 in the browser. Each route reads the form, calls the
logic in tracker.py, saves with store.py, and shows a page. The logic is tested in
tests/test_tracker.py and tests/test_actions.py; these routes in tests/test_app.py.
"""

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

import store
import tracker
from tracker import TrackerProblem

DATA_FILE = Path(__file__).parent / "data" / "tracker.json"
PERIOD_NAMES = {"day": "daily", "week": "weekly", "month": "monthly", "year": "yearly"}


def create_app(data_file=DATA_FILE, now=datetime.now):
    """Make the app. Tests pass a temporary data_file and a fake `now` clock."""
    app = Flask(__name__)
    app.secret_key = os.urandom(16)  # only for the one-line messages after a button press

    def current_time():
        return now().replace(microsecond=0)

    def load_state():
        """Load the saved state, closing a clock whose tab was closed (spec 3)."""
        state = store.load(data_file)
        if state is not None and tracker.close_abandoned(state, current_time()):
            store.save(data_file, state)
        return state

    def change(action):
        """Load, run action(state, now), save. A TrackerProblem is shown and nothing is saved."""
        state = load_state()
        if state is None:
            return False
        try:
            action(state, current_time())
        except TrackerProblem as problem:
            flash(str(problem))
            return False
        store.save(data_file, state)
        return True

    @app.errorhandler(store.StoreProblem)
    def damaged_file(problem):
        return render_template("error.html", message=str(problem)), 500

    @app.context_processor
    def clock_for_every_page():
        """Every page shows a running clock and keeps checking in while it is open."""
        try:
            state = store.load(data_file)
        except store.StoreProblem:
            state = None  # the error page explains it; don't fail again here
        running = tracker.running_session(state) if state else None
        return {
            "running": running,
            "running_seconds": tracker.session_seconds(running, current_time()) if running else 0,
            "check_in_ms": tracker.CHECK_IN_SECONDS * 1000,
            "clock": tracker.format_clock,
        }

    # --- Pages ---

    @app.get("/")
    def main_page():
        state = load_state()
        if state is None:
            return render_template("setup.html", periods=PERIOD_NAMES)
        moment = current_time()
        goal = state.goal
        return render_template(
            "main.html",
            message=tracker.top_message(state),
            deadlines=[(i, tracker.deadline_text(d, moment)) for i, d in tracker.deadlines_in_order(state)],
            progress=tracker.progress(state, moment),
            past=tracker.past_period_text(state, moment),
            goal_text=f"{tracker.format_duration(goal.minutes)} {PERIOD_NAMES[goal.period]}",
            goal=goal,
            periods=PERIOD_NAMES,
            rows=tracker.day_rows(state, moment),
            duration=tracker.format_duration,
            done_vs_goal=tracker.format_done_vs_goal,
        )

    @app.get("/day/<day_text>")
    def day_page(day_text):
        state = load_state()
        if state is None:
            return redirect(url_for("main_page"))
        moment = current_time()
        day = _day_in_list(state, day_text, moment.date())
        # The index in state.sessions is what the Edit and Delete buttons send back.
        rows = sorted(
            (
                (index, s, tracker.session_seconds(s, moment) // 60)
                for index, s in enumerate(state.sessions)
                if s.start.date() == day
            ),
            key=lambda row: row[1].start,
        )
        total = tracker.minutes_between(state.sessions, _midnight(day), _midnight(day) + ONE_DAY, moment)
        return render_template(
            "day.html",
            day=day,
            day_title=_day_title(day),
            rows=rows,
            total=total,
            is_today=day == moment.date(),
            duration=tracker.format_duration,
        )

    # --- Buttons ---

    @app.post("/setup")
    def setup():
        if store.load(data_file) is not None:
            return redirect(url_for("main_page"))  # the goal is only set up once
        try:
            minutes = tracker.parse_amount(request.form.get("hours", ""), request.form.get("minutes", ""))
            state = tracker.new_state(minutes, request.form.get("period", ""), current_time())
        except TrackerProblem as problem:
            flash(str(problem))
            return redirect(url_for("main_page"))
        store.save(data_file, state)
        return redirect(url_for("main_page"))

    @app.post("/goal")
    def change_goal():
        def action(state, moment):
            minutes = tracker.parse_amount(request.form.get("hours", ""), request.form.get("minutes", ""))
            tracker.set_goal(state, minutes, request.form.get("period", ""), moment)

        if change(action):
            flash("Goal changed. It counts from 0 starting now.")
        return redirect(url_for("main_page"))

    @app.post("/reset")
    def reset():
        if request.form.get("sure") != "yes":
            flash("Nothing was reset.")
        elif change(tracker.reset):
            flash("Reset. Progress counts from 0 starting now; all your days are still saved.")
        return redirect(url_for("main_page"))

    @app.post("/deadlines")
    def add_deadline():
        def action(state, moment):
            day = _parse_date(request.form.get("date", ""), "Please pick the deadline's date.")
            time_text = request.form.get("time", "").strip()
            due_time = _parse_time(time_text, "Please pick a time, or leave it empty.") if time_text else None
            tracker.add_deadline(state, request.form.get("name", ""), day, due_time)

        change(action)
        return redirect(url_for("main_page"))

    @app.post("/deadlines/<int:index>/remove")
    def remove_deadline(index):
        change(lambda state, moment: tracker.remove_deadline(state, index))
        return redirect(url_for("main_page"))

    @app.post("/day/<day_text>/sessions")
    def add_session(day_text):
        state = load_state()
        if state is None:
            return redirect(url_for("main_page"))
        day = _day_in_list(state, day_text, current_time().date())

        def action(state, moment):
            start = _parse_time(request.form.get("start", ""), "Please pick the time the session started.")
            minutes = tracker.parse_amount(request.form.get("hours", ""), request.form.get("minutes", ""))
            tracker.add_manual_session(state, day, start, minutes, moment)

        if change(action):
            flash("Session added.")
        return redirect(url_for("day_page", day_text=day.isoformat()))

    @app.post("/sessions/<int:index>/edit")
    def edit_session(index):
        was = _parse_was(request.form.get("was", ""))

        def action(state, moment):
            start = _parse_time(request.form.get("start", ""), "Please pick the time the session started.")
            minutes = tracker.parse_amount(request.form.get("hours", ""), request.form.get("minutes", ""))
            tracker.edit_session(state, index, was, start, minutes, moment)

        if change(action):
            flash("Session changed.")
        return redirect(url_for("day_page", day_text=was.date().isoformat()))

    @app.post("/sessions/<int:index>/delete")
    def delete_session(index):
        was = _parse_was(request.form.get("was", ""))
        if request.form.get("sure") != "yes":
            flash("Nothing was deleted.")
        elif change(lambda state, moment: tracker.delete_session(state, index, was)):
            flash("Session deleted.")
        return redirect(url_for("day_page", day_text=was.date().isoformat()))

    @app.post("/clock/start")
    def start_clock():
        change(tracker.start_clock)
        return redirect(url_for("day_page", day_text=current_time().date().isoformat()))

    @app.post("/clock/stop")
    def stop_clock():
        state = store.load(data_file)
        running = tracker.running_session(state) if state else None
        if running is None:
            flash("No clock is running.")
            return redirect(url_for("main_page"))
        day_url = url_for("day_page", day_text=running.start.date().isoformat())
        if tracker.close_abandoned(state, current_time()):
            # The page stopped checking in (tab closed, or the computer slept) before Stop.
            store.save(data_file, state)
            last = running.last_seen or running.start
            flash(
                f"The clock had already stopped at {tracker.format_clock(last)}, when this page "
                "stopped checking in (closed tab or sleeping computer). That part is saved."
            )
            return redirect(day_url)
        tracker.stop_clock(state, current_time())
        store.save(data_file, state)
        flash("Session saved.")
        return redirect(day_url)

    @app.post("/clock/check-in")
    def check_in():
        """Called by the open page every 30 seconds while the clock runs (spec 3)."""
        state = load_state()
        if state is None or not tracker.check_in(state, current_time()):
            return jsonify(running=False)
        store.save(data_file, state)
        return jsonify(running=True)

    return app


# --- Small helpers for reading the URL and forms ---

ONE_DAY = timedelta(days=1)


def _midnight(day):
    return datetime(day.year, day.month, day.day)


def _day_title(day):
    return f"{day:%a} {day:%b} {day.day}"


def _day_in_list(state, day_text, today):
    """The day from the URL if it is in the list (first run to today), else "not found"."""
    try:
        day = date.fromisoformat(day_text)
    except ValueError:
        abort(404)
    if not state.first_run <= day <= today:
        abort(404)
    return day


def _parse_date(text, message):
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise TrackerProblem(message) from None


def _parse_was(text):
    """The session's start as the page saw it (hidden in the Edit and Delete forms)."""
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        abort(400)


def _parse_time(text, message):
    try:
        return time.fromisoformat(text.strip())
    except ValueError:
        raise TrackerProblem(message) from None


if __name__ == "__main__":
    print("Study tracker is running. Open http://127.0.0.1:5000 in your browser.")
    print("Press Ctrl+C here to stop it.")
    create_app().run(host="127.0.0.1", port=5000)
