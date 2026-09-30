# Moon 🌙

A small, local-first Linux companion CLI for daily messages, period notes, hydration reminders, and alarms.

> **MVP note:** This is a one-take starter, not a medically validated tracker or a production-hardened daemon. It stores data locally in `~/.config/moon/moon.json` so it works immediately and offline. Google Sheets sync is intentionally an adapter-sized next step: do not put service-account credentials in this public repository.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
moon --help
moon help
moon set-volume
```

## Google Sheets period records

Install the optional Sheets dependencies and copy `.env.example` to `.env`:

```bash
pip install -e '.[sheets]'
cp .env.example .env
```

Create a Google Cloud service account, enable the Google Sheets API, download its
JSON key, and share the target spreadsheet with the service account email as an
Editor. Set `GOOGLE_SHEETS_CREDENTIALS`, `MOON_PERIOD_SPREADSHEET_ID`, and
`MOON_PERIOD_WORKSHEET` in `.env`.

Moon creates the worksheet and headers automatically. Each record stores Date,
Time, Note, Feedback, and Recorded At. Reusing a date and time updates the
existing row. Without complete Sheets configuration, `track` and `report` use
local JSON and identify that in the command output; partial configuration is an
error rather than a mixture of local and remote data.

## Examples

```bash
moon track 2026-09-27 "Started today" "mild cramps" --time 08:30
moon report 2026-09-27
moon report                 # opens an interactive date prompt
moon message set 2026-09-27 "Good {time_of_day}, my love!"
moon message show
moon hydration              # interactive setup
moon alarm set              # interactive setup
moon daemon                 # keep running for scheduled items
```

Time accepts `13:00`, `1:00 PM`, `1:00pm`, and an interactive clock-style prompt. Bare ambiguous times such as `1:00` ask for AM/PM.

## Background operation

Run `moon daemon` in a terminal to test. For automatic startup, install a user systemd service (see `systemd/moon.service.example`). Notifications use `notify-send` when available; otherwise they print to the terminal. Audio playback tries `paplay`, `ffplay`, then `aplay`.

The Debian package installs and enables `moon-personal.service` automatically. It runs continuously under a dedicated unprivileged `moon` account and stores its state in `/var/lib/moon`. For notifications and audio in the logged-in desktop session, also enable the packaged user service with `systemctl --user enable --now moon-personal-user.service`.

The alarm sound path is configurable. Moon attempts to cap the system volume at 50% using `wpctl` or `pactl`, then restores the previous value after playback. **A percentage is not a universal loudness/safety guarantee**; test on the target laptop and headphones.

## Data and privacy

- Local JSON is the explicit fallback when Google Sheets is not configured.
- This repository contains no personal data or credentials.
- Period predictions are not included in this MVP; cycle estimates require enough history and should be treated as estimates.
- The daemon needs the laptop awake to fire alarms/reminders. Missed events are skipped rather than replayed in a burst.


## Sounds and GUI

Place `alarm.<ext>` and `hydration.<ext>` in `sounds/`; blank sound paths use these named files. `moon set-volume` configures separate playback levels for detected headphones/earphones and speakers. Detection depends on audio-device metadata. Time prompts use a small 12-hour GUI picker when a desktop is available; `moon report` without a date opens a calendar.
