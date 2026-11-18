# Study tracker: spec

What the program does, exactly. The requirements are in `problem.md`; this file turns them
into behaviour that can be built and tested. "Bullet N" means the Nth bullet under
*Initial requirements* in `problem.md`, and "later bullet N" the Nth bullet under
*Later requirements*.

## How to run

```
python app.py
```

Then open <http://127.0.0.1:5000> in the browser. It runs only on your own computer, with
no login and no internet. All times are your computer's local time (bullet 4).

## 1. First run: the goal (bullets 5, 12)

The very first time, before anything else, the page asks for a goal:

- **Amount**: hours and minutes, for example 10 h 0 min, or 0 h 45 min. 0 is allowed.
- **Period**: a box with Daily / Weekly / Monthly / Yearly.

The goal can be changed at any time from the main page. A new goal starts counting from 0
at the moment it is set. Older days and sessions stay saved and still show in the list.

## 2. The main page: days like folders (bullets 3, 6, 7, 8)

The top of the page shows, in this order:

1. **The message**: "time to work hard!!" if the goal is above 0, or "have a great off
   day!!" if the goal is 0.
2. **Countdowns** for each deadline (section 6).
3. **Progress** in the current period (section 4): for example
   "This week: 4 hours of 10 hours, 40% completed".
4. **Extra hours**, if the goal is passed in this period: "Extra hours: 2 hours".
5. **Past period**: "past week = 4/10 hours" (section 5).

Below that is **the list of days**, newest first, like folders. There is one row for every
day from the day the program was first run up to today, **including days with no hours**
(they show 0). Each row shows the date and that day's total, such as
"Mon Nov 16: 2h 30min". For a daily goal, each day also shows whether it reached the goal.
If the goal is 0, every day counts as reached.

Clicking a day opens it (section 3).

## 3. A day's page: the sessions (bullets 4, 9)

It lists every session that day: when it started, how long it lasted, and when it ended,
in the computer's local time (for example "2:05 PM - 3:35 PM, 1h 30min"). It also shows
how many sessions there were and the day's total.

The **Add a session** button gives two choices:

- **Start the clock**: a running timer. Press **Stop** to end the session.
  - If the tab is closed while the clock is running, the session is saved up to the moment
    the tab was closed. The open page tells the program "still here" every 30 seconds. A
    running session that hasn't checked in for over 90 seconds ends at its last check-in.
  - Only one clock can run at a time.
- **Add it by hand**: the start time, plus hours and minutes. This is for a session you
  forgot to time, including on past days. A session can't be in the future, can't be 0
  minutes, and can't be longer than 24 hours.

A session belongs to the day it started on.

### Editing and deleting a session (later bullet 1)

Each session on a day's page has an **Edit** and a **Delete** button.

- **Edit** changes a finished session's **start time** and **length** (hours and
  minutes). The session stays on the same day; to move it to another day, delete it and
  add it there. The same rules as adding by hand apply: at least 1 minute, at most 24
  hours, and **it can't end in the future**. So at 10 PM a session can't be set to start
  at 11 PM (or to start at 9:30 PM and last an hour); the page says why and nothing
  changes. A session whose clock is still running can't be edited: press Stop first.
- **Delete** asks "Are you sure?" first, then removes the session for good. A session
  whose clock is running can be deleted too; that cancels the clock.
- If the session was already changed or deleted (for example in another tab), the page
  says so and nothing changes.
- Totals, progress and the past period follow the edited session. Progress still counts
  only sessions that start at or after the goal was set or the last reset (section 4), so
  moving a session's start to before a reset takes it out of the current progress.

## 4. Progress in the current period (bullets 8, 10, 12)

- The **current period** is today, this week (Monday to Sunday), this calendar month, or
  this calendar year, depending on the goal.
- **Done** = the minutes of sessions in the current period that started after the goal
  was set (or after the last reset, whichever is later).
- **% completed** = done ÷ goal × 100, rounded to the nearest whole %, with .5 going up.
  It can be above 100%. With a goal of 0 it shows "no goal" instead of a %.
- **Extra** = done − goal, shown only when it is above 0.

## 5. Past period (bullet 10)

"past week* = 4/10 hours*" shows the hours done in the previous period against the goal.
The word follows the period: past day, past week, past month, past year. It shows 0 if no
hours were done then, or if there was no previous period yet (the first period).

## 6. Deadlines (bullets 10, 11)

- Optional. There can be several, each with a **name** and a **date**, plus an optional time
  (otherwise it means the end of that day, 11:59 PM).
- Before the deadline, the top of the page shows how many days are left:
  "CSC 300 final: 5 days left", "1 day left", "today".
- After it passes, it shows how long ago it was, in the biggest whole unit:
  "Essay: 3 days past deadline", "5 hours past deadline", "20 minutes past deadline".
- A deadline stays until the user removes it. Nothing is removed automatically.

## 7. Reset (bullet 10)

Only the user can reset, with a **Reset** button that asks "Are you sure?" first.
Progress then starts again from 0 at that moment. Every day and session stays saved and
still shows in the list. Nothing else resets on its own: a goal being reached or a deadline
passing never resets anything.

## 8. Showing amounts of time (bullet 10)

Amounts follow the unit you used for the goal, so a 45-minute goal stays in minutes:

- Under one hour: "45min". Whole hours: "1 hour", "10 hours". Otherwise: "4h 30min".
- Done against goal, like "past week = 4/10 hours", is shown that short way when both
  amounts are whole hours, or both are under an hour ("30/45 min"). Otherwise both are
  written in full: "4h 30min / 10 hours".

## 9. Saving

Everything is saved in `data/tracker.json`, right after each change. That file holds your
real study data, so it is not put on GitHub (it is in `.gitignore`).

## 10. Tests

`python -m pytest`. Tests cover the logic: periods, totals, %, extra and past-period
amounts, showing amounts of time, deadlines, the timer check-in rule, checking hand-added
sessions, editing and deleting sessions, reset, and saving/loading. Flask's test client
checks that each button changes the saved data correctly. The page layout and colours are not tested.

## Decisions I made that problem.md doesn't say (please check)

1. The list of days starts on the day the program was first run.
2. A session belongs to the day it started, even if it goes past midnight.
3. The timer checks in every 30 seconds. A tab gone for more than 90 seconds ends the
   session at its last check-in, so up to 30 seconds can be lost.
4. Only one clock can run at a time.
5. A hand-added session needs a start time, can't be in the future, and must be between
   1 minute and 24 hours long.
6. % can go above 100%, and Extra hours are shown too.
7. A deadline without a time means 11:59 PM that day.
8. Editing or deleting a session was left out at first; later bullet 1 added it (section
   3, and decisions 14 to 17).
9. Data is saved in `data/tracker.json` and kept off GitHub.
10. A hand-added session can't be on a day before the first run, since that day wouldn't
    be in the list.
11. If the tab is closed before the clock's first check-in (under 30 seconds), no session
    is kept, rather than an empty 0-minute one.
12. Sessions are allowed to overlap. The program doesn't check whether two sessions cover
    the same time.
13. If the computer goes to sleep with the clock running, the session ends at the last
    check-in before the sleep (sleeping isn't studying).
14. Editing changes only the start time and length; the session stays on its day. To move
    it to another day, delete it and add it again there.
15. "Not in the future" means a session can't **end** after now, for adding and for
    editing. That covers the 11 PM example in later bullet 1, and also a session that
    starts in the past but would run past now.
16. A running session can be deleted (this cancels the clock) but not edited; press Stop
    first.
17. Deleting asks "Are you sure?" first, because a deleted session can't be brought back.

## Known small issues (left as they are for now)

1. The Edit form works in whole minutes. A clock-timed session keeps its seconds (for
   example 2:00:17 PM to 3:30:05 PM), but the form shows it as 2:00 PM and 1h 29min.
   Saving the form, even without changing anything, stores those whole minutes, so the
   session can lose up to a minute.
