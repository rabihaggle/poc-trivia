# English Level Trivia

A small Flask web app that estimates a player's English level (CEFR A1–C2) through a
10-question multiple-choice quiz, adapts the difficulty across attempts, and gives
admins tools to manage the question bank and review results.

**Live demo:** https://trivia-poc.onrender.com

## Features

- **Google Sign-In** — players and admins authenticate with their Google account; no
  passwords are stored by the app.
- **Adaptive CEFR leveling** — every new player starts at A1. Scoring more than 6/10
  levels them up one CEFR step (A1 → A2 → B1 → B2 → C1 → C2) for their *next* attempt;
  C2 is the ceiling. The level is calculated from the player's most recent attempt.
- **180-question bank** — 30 questions per CEFR level, each with 1 correct and 2+
  wrong answers. A quiz samples 10 questions from the player's current level.
- **Full attempt history** — every question a player answered, what they picked, and
  the correct answer are persisted per attempt (not just the final score), with a
  timestamp.
- **Ranking page** — all attempts sorted by score.
- **Admin panel** (`/admin`), gated to an email allow-list:
  - Create/delete questions, each tagged with a CEFR level.
  - **CSV export/import for the question bank** (bulk-edit in a spreadsheet, re-upload).
  - **Results by user** — every player's attempts, with a per-attempt breakdown of
    which question, what they answered, and whether it was correct.
  - **CSV export for results**, filterable by user and/or date range, in either
    per-question detail or per-attempt summary format.
  - **Dashboard** — KPIs (players, attempts, average score, level-ups, bank size),
    players by current level, attempts by level played, question bank composition,
    and a recent activity feed.

## Tech stack

- **Backend:** Python, Flask, `gunicorn` (production WSGI server)
- **Auth:** Google OAuth 2.0 via [Authlib](https://authlib.org/)
- **Database:** SQLite (file-based, via the standard `sqlite3` module)
- **Frontend:** server-rendered Jinja templates + vanilla JS/CSS (no build step)
- **Hosting:** [Render](https://render.com) (free tier), deployed from this repo via
  [`render.yaml`](render.yaml)
- **Keep-alive:** a [GitHub Actions workflow](.github/workflows/keep-alive.yml) pings
  the app every 10 minutes so Render's free tier doesn't spin it down

## Project structure

```
app.py                    Flask app: routes, auth, leveling logic, CSV import/export
database.py                SQLite connection + schema (init_db)
seed.py                    180-question sample bank, loaded on first boot if empty
requirements.txt           Python dependencies
render.yaml                 Render Blueprint (build/start commands, env vars)
.github/workflows/          GitHub Actions (keep-alive ping)
templates/
  base.html                 Shared HTML shell
  index.html                 Login screen + quiz UI
  admin.html                 Question CRUD + CSV import/export
  admin_dashboard.html       Usage dashboard
  admin_results.html         All players, with current level and CSV export
  admin_user_results.html    One player's full attempt history
  ranking.html                Public leaderboard
  forbidden.html              Shown to logged-in non-admins hitting /admin*
  _user_bar.html              Shared "logged in as ..." header partial
static/
  css/style.css              All styling
  js/game.js                  Quiz UI logic (fetches /api/quiz, submits answers)
```

## Database schema

SQLite, created by `database.init_db()`. Foreign keys cascade on delete.

| Table              | Purpose                                                                 |
|---------------------|--------------------------------------------------------------------------|
| `questions`         | `id, text, level (A1-C2), created_at`                                    |
| `correct_answers`   | One row per question (`question_id` is `UNIQUE`): `id, question_id, text` |
| `wrong_answers`     | N rows per question: `id, question_id, text`                             |
| `attempts`          | One row per quiz played: `id, email, name, level, score, total, played_at` |
| `attempt_answers`   | One row per question answered in an attempt: `id, attempt_id, question_id, question_text, level, selected_text, correct_text, is_correct` |

`attempt_answers` snapshots the question/answer text at the time it was played, so the
history stays meaningful even if a question is later edited or deleted.

> **Note:** Render's free tier gives the app an ephemeral filesystem — the SQLite file
> is recreated from scratch (and reseeded with the sample questions) on every deploy.
> Anything loaded or played between deploys is lost. For real persistence, either add a
> Render persistent disk or migrate to a managed database (e.g. Postgres).

## Environment variables

| Variable               | Required | Description                                                                 |
|--------------------------|:--------:|-------------------------------------------------------------------------------|
| `SECRET_KEY`             | Yes      | Signs the session cookie. On Render this is auto-generated (`render.yaml`). |
| `GOOGLE_CLIENT_ID`       | Yes      | OAuth 2.0 Client ID from Google Cloud Console.                              |
| `GOOGLE_CLIENT_SECRET`   | Yes      | OAuth 2.0 Client Secret from Google Cloud Console.                          |
| `ADMIN_EMAILS`           | Yes      | Comma-separated list of Google emails allowed into `/admin*`.               |
| `PORT`                   | No       | Port to listen on locally (defaults to 5000).                               |
| `PYTHON_VERSION`         | No       | Pinned in `render.yaml` for the Render build.                               |

None of these are committed to the repo (it's public) — they're set as environment
variables locally (shell/`.env`) and in the Render dashboard.

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY="dev-secret"
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."
export ADMIN_EMAILS="you@gmail.com"

python3 app.py   # http://localhost:5000
```

The database (`trivia.db`) and the 180-question sample bank are created automatically
on first run (`init_db()` + `seed()` run at import time in `app.py`).

### Setting up Google OAuth credentials

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project.
2. **APIs & Services → OAuth consent screen**: type *External*; while in *Testing*
   mode, add every Google account that should be able to sign in under "Test users".
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**, type
   *Web application*:
   - Authorized JavaScript origins: your app's URL (e.g. `http://localhost:5000`,
     `https://trivia-poc.onrender.com`)
   - Authorized redirect URIs: `<your app's URL>/auth/callback`
4. Copy the generated Client ID and Client Secret into `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET`.

## Deployment (Render)

1. Push this repo to GitHub.
2. In [Render](https://render.com), **New + → Blueprint**, pick the repo. Render reads
   [`render.yaml`](render.yaml) and configures the build (`pip install -r
   requirements.txt`) and start (`gunicorn app:app`) commands automatically.
3. In the service's **Environment** tab, set `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, and `ADMIN_EMAILS` (`SECRET_KEY` is auto-generated).
4. Every push to `main` triggers an automatic redeploy.

## Known limitations (PoC scope)

- SQLite storage is ephemeral on Render's free tier — resets on every deploy (see
  above).
- No question *editing* — only add (form or CSV import) and delete.
- Admin access is a static email allow-list (env var), not a roles/permissions system.
- No automated tests; verification has been manual + ad hoc scripts during development.
- Render's free tier cold-starts after ~15 minutes idle; the GitHub Actions keep-alive
  workflow mitigates this but isn't a guarantee.
