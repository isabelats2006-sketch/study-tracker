# Study tracker

A small web app that keeps track of your study sessions and how close you are to your
study goal. It runs on your own computer and you use it in the browser.

- Set a goal (hours and minutes, daily, weekly, monthly or yearly). A goal of 0 means an
  off day.
- The main page lists every day like a folder, with that day's total, including days with
  no hours. It shows "This week: 4 hours of 10 hours, 40% completed", extra hours, how the
  past period went ("past week = 4/10 hours"), and countdowns to your deadlines.
- Open a day to see its sessions (start, end, length), then start the clock or add a
  session by hand, including on past days.
- If the tab is closed while the clock runs, the session is saved up to that moment.
- Only you can reset progress. Your days and sessions stay saved.

Python 3.13 or newer with Flask. Tests use pytest. No login and no internet needed.

## Run it

```
python app.py
```

Then open <http://127.0.0.1:5000> in your browser. Press Ctrl+C in the terminal to stop it.

(Install Flask first if you don't have it: `python -m pip install flask`.)

## Run the tests

```
python -m pytest
```

(Install pytest first if you don't have it: `python -m pip install pytest`.)

## Where the data goes

Everything is saved in `data/tracker.json`, which is never put on GitHub. To start over
completely, stop the app and move that file somewhere else. The full rules are in
`spec.md`.
