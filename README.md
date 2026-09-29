# Geocaching Hunt Planner

A Flask web app for organising **geocaching hunts**: a creator draws an area on a map,
drops a set of cache waypoints with clues, and players race to find them all and upload
a proof photo for each one. The first player to complete every cache is declared the
winner, pending the creator's validation.

> **Warning — educational project, not a production application.** This is a personal
> learning project, released as-is. It has no automated tests, no CSRF protection on its
> state-changing routes, no rate limiting, and it stores uploaded photos as uncompressed
> base64 blobs inside MongoDB documents. Do not deploy it with real user data, and do not
> treat it as a reference implementation. See
> [Known limitations](#known-limitations).

> **Status: dormant.** Version 1 was developed and deployed in January 2025, but the
> Fly.io app and the MongoDB Atlas cluster it pointed at no longer exist — both
> hostnames fail DNS resolution. The code is complete and runnable; the infrastructure
> is not. See [Current status](#current-status).

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Current status](#current-status)
- [Known limitations](#known-limitations)
- [Running it locally](#running-it-locally)
- [Environment variables](#environment-variables)
- [Setting up Google OAuth](#setting-up-google-oauth)
- [Setting up MongoDB](#setting-up-mongodb)
- [Deployment](#deployment)
- [Project structure](#project-structure)
- [License](#license)

---

## Features

**Authentication**
- Google OAuth 2.0 / OpenID Connect via Authlib. No passwords stored, ever.
- Flask signed-cookie sessions. The OAuth access token is stored client-side in the
  session cookie (see [limitations](#known-limitations)).

**Creating a hunt** (`/newGame`)
- Draw the hunt bounding box on a Leaflet map — the box defines the hunt area.
- Place cache markers inside the area. Each marker carries a text clue and an optional
  clue image.
- Markers can be edited or deleted after placement via Leaflet.draw.
- "Locate me" button centres the map on the creator's GPS position.

**Playing a hunt** (`/game/<name>`)
- Join or leave an in-progress hunt.
- Each cache is a collapsible card showing its clue.
- Mark a cache as found and upload a proof photo. Both the flag and the photo can be
  withdrawn while the hunt is in progress.
- The hunt switches to **In revision** the moment *any* player completes every cache;
  that player becomes the provisional winner.

**Supervision** (`/view_game/<name>`, creator only)
- Per cache, see which players found it, with their proof photo and timestamp.
- Remove any player's answer. If it belonged to the provisional winner, the hunt
  reverts to **In progress** and the winner is cleared.
- Clear the winner, reset the hunt, or delete it entirely.
- Validate the winner to move the hunt to **Completed**.

**Browse**
- `/home` — global hunts (everything you did not create), grouped by status, newest first.
- `/myHunts` — hunts you are subscribed to.
- `/huntCreations` — hunts you created.

**Hunt lifecycle**

| Status | Meaning |
|---|---|
| `In progress` | Open. Players may join, find caches, and upload photos. |
| `In revision` | Somebody found everything. The creator must confirm or clear the winner. |
| `Completed` | Winner validated. Locked. |

---

## Tech stack

**Backend** — Python 3.12, Flask 3.0, Authlib 1.3, PyMongo 4.10, python-dotenv, gunicorn.
**Frontend** — server-rendered Jinja2 templates, vanilla JS, no build step, no bundler.
Leaflet 1.7.1, Leaflet.draw 1.0.4, SweetAlert2 11 — all loaded from a CDN.
**Database** — MongoDB (two collections: `Games` and `User_games`).
**Infrastructure** — Docker on Fly.io, region `fra`, 1 GB RAM / 1 shared CPU,
continuous deployment from GitHub Actions. The infrastructure is configured but
currently torn down; see [Current status](#current-status).

There is no client-side toolchain. If you change a template, refresh the page.

---

## Current status

**The code is complete. The infrastructure is gone.**

Authentication, hunt creation, participation, proof upload, winner detection,
supervision, and the three-state lifecycle are all implemented. Version 1 was finished
and shipped in January 2025 — the last commit is `194cf72`, dated 2025-01-18, and the
project has been untouched since.

What is **not** true today is that any of it is running:

- `geocaching-app-paas02.fly.dev` does not resolve. Fly.io assigns a `*.fly.dev`
  hostname when an app is created and keeps it regardless of whether the machine is
  stopped, so a NXDOMAIN means the app itself is gone.
- The MongoDB Atlas cluster referenced by the committed `.env` does not resolve either.
  Atlas deletes free-tier M0 clusters after a period of inactivity, which is the most
  likely explanation 20 months on.
- Consequently `import app` currently fails at `MongoClient(MONGODB_URI)` in
  `backend/database.py:12`. The connection is lazy for ordinary operations, but an
  `mongodb+srv://` URI is DNS-resolved eagerly at construction, so a bad host name
  crashes the process at import time rather than on the first query.

Bringing it back up means creating a fresh cluster and app and pointing `.env` at them.
The deploy instructions in [Deployment](#deployment) are written for a new app; note
that `fly.toml` still hardcodes the old app name.

**Not built yet.** There is no test suite of any kind, and the CI pipeline does not run
tests — it only deploys. There are no database migrations or seed scripts, no pagination,
no rate limiting, and no internationalisation (the UI is English, with a few leftover
Spanish strings in `templates/mainpage.html`).

**Dead code and config drift** worth knowing before you touch anything:

- `backend/gameController.py` is an empty file. Nothing imports it.
- The `[TIMEZONE]` section of `appConfig.ini` is read by nobody. Related: every
  timestamp is produced by a naive `datetime.now()`, so stored dates carry no timezone
  and will differ depending on which machine wrote them.
- `gunicorn` is pinned in `requirements.txt` but the `Dockerfile` starts the Flask
  development server instead. It works; it is just not the recommended way to serve
  this in production.
- `Status.NONE` in `backend/statusEnum.py:3` is declared as a bare annotation rather
  than a tuple assignment, so it is not a real enum member.

---

## Known limitations

Read this before deploying a fork.

**1. Images are stored as base64 inside MongoDB documents.**
Uploaded photos are read client-side with `FileReader.readAsDataURL` and written
verbatim into the `User_games` collection as data URLs (`templates/game.html:299`).
There is no client-side resize, no image re-encoding, and no object storage backend.
Base64 inflates payloads by roughly 33%, and MongoDB hard-caps a document at 16 MB.
A single modern phone photo can exceed that, and when it does the write fails with an
opaque driver error. A hunt with many players can hit the same ceiling sooner.
The first thing you should do in a fork is move this to GridFS or S3-compatible storage
and store only the URL.

**2. No CSRF protection.** The `POST` endpoints read a JSON body and trust it. Combined
with cookie-based sessions, this is exploitable by a third-party page. Not currently
exploitable in a damaging way because the blast radius is "upload a photo as myself",
but it should be fixed.

**3. No rate limiting or upload validation.** Any authenticated user can post to
`/uploadFoundImage` in a loop. Nothing checks the declared size server-side, and nothing
stops a base64 payload that is not actually an image.

**4. The OAuth access token lives in the session cookie.** Flask's default session
serializer is signed, not encrypted, so the token is readable by the client. Switching
to server-side sessions would fix this.

**5. Authorisation is checked ad hoc.** Each route repeats
`if "user" not in session: abort(404)` and each creator-only route re-implements its own
`sub` comparison. There is no decorator or middleware, so a missed check is a silent
authorisation bug.

**6. No indexes.** Queries such as `find_all_user_games` and `get_num_players_from_game`
run as collection scans and are called once per hunt on the browse pages. This will
degrade with data volume.

**7. Single-region deployment.** One Fly.io machine in `fra`, `min_machines_running = 0`.
No health checks, no backups, no staging environment. MongoDB Atlas is the only thing
backing your data.

**8. `appConfig.ini` is read through a relative path.** `backend/database.py:14` calls
`config_parser.read('appConfig.ini')` with no directory, so the process must start from
the repository root or it will crash on import.

---

## Running it locally

**Prerequisites** — Python 3.12+, a Google Cloud project, and a MongoDB Atlas cluster.

```bash
git clone https://github.com/FeelNostalgic/PaaS.git
cd PaaS

python -m venv .venv
```

**Windows**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Then:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in the four values — see [Environment variables](#environment-variables),
plus the [OAuth](#setting-up-google-oauth) and [MongoDB](#setting-up-mongodb) sections
for how to obtain them.

Run it:

```bash
python app.py
```

The app starts on `http://localhost:8080` with the Flask debugger enabled. Open that URL
and sign in with Google. Nothing is seeded — you will start with an empty list, so use
**Plan a hunt** to create the first one.

If you prefer Flask's own entry point, `flask --app app run --port 8080` is equivalent.

> **Note on `requirements.txt`** — it pins `pymongo` directly. SRV connection strings
> (`mongodb+srv://`) need DNS resolution, which comes from `dnspython`; it is listed and
> will be installed, so Atlas URIs work. If you ever install by hand rather than from the
> requirements file, use `pymongo[srv]` instead.

---

## Environment variables

Read by `python-dotenv` at import time. `.env` is gitignored — never commit it.

| Variable | Required | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Signs the Flask session cookie. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `CLIENT_ID` | Yes | Google OAuth 2.0 client ID. |
| `CLIENT_SECRET` | Yes | Google OAuth 2.0 client secret. |
| `MONGODB_URI` | Yes | MongoDB connection string. Atlas SRV URI recommended. |

Collection names and the database name are **not** environment variables — they live in
the tracked `appConfig.ini`:

```ini
[TIMEZONE]
LOCAL_TIMEZONE = Europe/Madrid

[MONGO]
MONGO_DB = GeocachingDB
GAMES_COLLECTION = Games
USER_GAMES_COLLECTION = User_games
```

`[TIMEZONE]` is currently unused (see [Current status](#current-status)). The file is
safe to commit because it contains no credentials.

If a variable is missing, `app.py` falls back to the literal string
`clave_por_defecto` for the Flask and OAuth secrets, which will fail confusingly at
runtime. `MONGODB_URI` has no fallback — `backend/database.py` reads it with
`os.environ[...]` and raises `KeyError` on startup if it is unset.

---

## Setting up Google OAuth

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create or pick
   a project.
2. Enable the **Google People API** (or Identity Platform) for that project.
3. Go to **APIs & Services → Credentials** and create an **OAuth client ID** of type
   **Web application**.
4. Under **Authorised redirect URIs**, add exactly:

   ```
   http://localhost:8080/auth/callback
   ```

   The path is not configurable — it is hardcoded to the `auth_callback` route in
   `app.py`. For a deployed instance, add your production origin too, e.g.
   `https://your-app.fly.dev/auth/callback`.
5. Copy the client ID and client secret into `.env` as `CLIENT_ID` and `CLIENT_SECRET`.
6. Add your own Google account (and any testers') to **Test users** while the OAuth
   consent screen is in *Testing* status. Google caps unverified apps at 100 test users.

The app requests only the `openid email profile` scopes. It reads the `sub` claim as the
user identifier and `given_name` as the display name.

---

## Setting up MongoDB

The cluster this project used to point at is gone, so you are creating a new one from
scratch. Any data from the old deployment is unrecoverable unless you still have an Atlas
backup.

1. Create a free **M0** cluster on [MongoDB Atlas](https://www.mongodb.com/atlas).
2. Under **Database Access**, create a user with *Read and write to any database*.
3. Under **Network Access**, allow your connections. During development the simplest
   option is to allow access from anywhere (`0.0.0.0/0`); tighten this before going to
   production.
4. Copy the **SRV** connection string. It looks like:

   ```
   mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority&appName=PaaS
   ```

5. Paste it into `.env` as `MONGODB_URI`.

The database and collection names are taken from `appConfig.ini` and are created
automatically on first write — there is no seeding step.

---

## Deployment

The app targets Fly.io. `fly.toml` pins the app name, region (`fra`), and machine size.
The app it names, `geocaching-app-paas02`, no longer exists. Pick a name, set it as `app`
in `fly.toml`, then create the app before the first deploy:

```bash
fly auth login
fly apps create <your-app-name>
fly deploy
```

Set the same four environment variables on the machine as Fly secrets, not in a file:

```bash
fly secrets set SECRET_KEY=... CLIENT_ID=... CLIENT_SECRET=... MONGODB_URI=...
```

Then update the OAuth redirect URI in Google Cloud to
`https://<your-app-name>.fly.dev/auth/callback`.

**Manual deploy**

**Continuous deployment**

`.github/workflows/fly-deploy.yml` deploys on every push to `main`. Add `FLY_API_TOKEN`
as a repository secret on GitHub to enable it. Generate the token with
`fly auth token`. To redeploy an existing commit without pushing, re-run the workflow
from the Actions tab.

**Docker directly**

```bash
docker build -t paas .
docker run -p 8080:8080 --env-file .env paas
```

The image is based on `python:3.12-slim`, installs `requirements.txt`, and listens on
port 8080.

---

## Project structure

```
.
├── app.py                  # All HTTP routes and the OAuth client setup
├── appConfig.ini           # Tracked config: database and collection names
├── requirements.txt        # Pinned Python dependencies
├── Dockerfile              # Container build for Fly.io
├── fly.toml                # Fly.io app configuration
├── .env.example            # Template for local environment variables
│
├── backend/
│   ├── __init__.py
│   ├── database.py         # The entire data layer. DatabaseAPI static methods.
│   ├── statusEnum.py       # Hunt status enum
│   └── gameController.py   # Empty. Dead file, nothing imports it.
│
├── templates/              # Jinja2 templates, one per view
│   ├── base.html           # Shared header, nav, and loading overlay
│   ├── login.html
│   ├── mainpage.html       # Global hunt list
│   ├── HuntGames.html      # My hunts
│   ├── HuntCreations.html  # Hunts I created
│   ├── newGame.html        # Hunt creation map
│   ├── game.html           # Hunt detail, player view
│   └── SuperviseGame.html  # Hunt detail, creator view
│
└── static/
    ├── css/                # One stylesheet per page area
    └── js/feedback.js      # SweetAlert2 + loading overlay helpers
```

All views are server-rendered and all mutations are plain `fetch` calls to routes in
`app.py`. There is no API layer and no client-side framework.

---

## License

[MIT](LICENSE) © 2025-2026 Francisco Aragonés

The MIT license grants you the right to use, copy, modify and redistribute this code. It
does not come with any warranty of fitness for a particular purpose — see the warning at
the top of this file. Use it to learn from, or as a starting point for something better.
