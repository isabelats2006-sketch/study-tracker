# CLAUDE.md: study tracker

A web app for my CSC 299 final project: a Flask server on my own computer, used in the
browser. Read `problem.md` (what it must do) and `spec.md` (exactly how) before changing
anything.

## Ground rules: the assignment's rules, never broken unless I say otherwise

- **problem.md is mine.** I write the requirements and any "Round N requirements" myself.
  Don't reword or add to it unless the assignment calls for it, and tell me first.
- **Requirements come first.** In a round, my requirements are committed and pushed before
  any spec, test or code change.
- **Tests for everything.** Every new or changed behaviour gets a pytest test, and
  `python -m pytest` must pass with 0 failed and 0 skipped. A skipped test has not passed.
  A test must fail if the code it checks were wrong. Only the logic needs tests, not the
  page layout. When requirements have IDs (R1, R2...), each test names the ID it checks.
- **Commits:** one change per commit. The message says what changed and why. Never
  "update", "fix", "wip" or similar. Never undo or amend a commit.
- **Show me every commit message before committing**, and wait for my OK. The assignment
  says I must read assistant-written messages before they are committed.
- **Push at least once on every day of work.**
- **Never in the repo:** `.jsonl` transcripts, `.venv`, `node_modules`, API keys or
  passwords, `data/` (my real study data), or any personal info. The repo is public.
- **README.md** always says what the program does, the command to run it, and the command
  to run the tests.
- **Runs with one command** on my computer. No API key, login, paid service or internet.
- **Ask before installing anything.** Flask and pytest are already installed.

## How to run

```
python app.py          # then open http://127.0.0.1:5000
python -m pytest       # run the tests
```

## Code notes

- Python 3.13 and Flask 3.1 on Windows, using Git Bash. No JavaScript libraries; the timer
  check-in is a few lines of plain JavaScript in the page.
- Logic (periods, totals, %, deadlines, the timer rule) is in plain Python functions that
  take "now" as an argument, so tests can pick any date and time. Flask code only reads
  the form, calls the logic, saves, and shows the page.
- Times are the computer's local time, stored as minutes or as ISO text
  ("2026-11-16T14:05:00").
