# Ladder

A self-hosted board for studying a technology topic by rungs: a topic is split into columns and its own difficulty
levels, every cell holds question cards, and you mark each one as known / review / unknown. The heart of it is an
interactive **question matrix** on a canvas: one column per section (Frameworks / Databases / Python /
Platform), cards inside a column ranked by the pool's own difficulty levels (`levels` in `pool.yaml`, 2–8;
base → junior → middle → senior by default).
A card is a question or a hands-on task plus a reference answer. Content lives in Markdown/JSON and
is imported into the question bank.

One screen carries the whole study session: filter the area, walk the matrix with the keyboard,
mark every card as known / review / unknown, and watch each track's coverage grow on the home page.

Stack: **FastAPI + SQLite** on the back end, **React + Vite + React Flow** on the front. Without
signing in it opens as a public demo (two tracks, in Russian and English); the full mode is behind a
login (local accounts, `owner` / `member` / `viewer` roles). Russian and English UI.

## What it looks like

Tracks are the entry point: the question count, how much of the track is already reviewed, its
sections, and the two things you actually do — open the board or open the question bank.

![Tracks](docs/screenshots/01-home.png)

|                                                                                                                                                                                                                                                     |                                                                                                                                                                                                                                          |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **The matrix.** A column per section, sub-columns inside it, cards ranked by the track's own levels; the filter panel dims every card that does not match the tag, level or search.<br><br>[![Question matrix](docs/screenshots/03-board.png)](docs/screenshots/03-board.png)                          | **The checklist from the keyboard.** `1 / 2 / 3` mark the current card known / review / unknown and move on, `n` jumps to the next unreviewed one; the HUD keeps the current card, its level and the running count, a dot on every card shows its status.<br><br>[![Checklist](docs/screenshots/04-checklist.png)](docs/screenshots/04-checklist.png) |
| **Full text next to the board.** A non-modal drawer: question, reference answer with syntax highlighting and the three status buttons, while the board stays interactive.<br><br>[![Answer drawer](docs/screenshots/05-drawer.png)](docs/screenshots/05-drawer.png) | **Hands-on tasks.** Besides questions the bank holds tasks: a statement, starter code, a reference solution and criteria to check yourself against.<br><br>[![Task](docs/screenshots/06-task.png)](docs/screenshots/06-task.png)          |
| **Question bank.** Full-text search and filters over the whole bank, any row expands to the full question and answer; questions are added and edited straight from the UI.<br><br>[![Question bank](docs/screenshots/07-bank.png)](docs/screenshots/07-bank.png) | **Track editor.** Sections, sub-columns and levels are data: rename, reorder by drag and drop, pick a colour from a fixed palette, preview the structure before saving.<br><br>[![Track editor](docs/screenshots/10-structure.png)](docs/screenshots/10-structure.png) |

The colour theme is one for the whole site: light by default, switched by the sun/moon button in every
header and remembered per browser.

![Dark theme](docs/screenshots/11-board-dark.png)

## Quick start

```bash
INTERVIEW_OWNER_PASSWORD=<password> ./run.sh   # venv + front-end build (if needed) + server
# http://localhost:8000 opens the demo; sign in at http://localhost:8000/#/login as owner@interview.local
```

The first launch seeds the owner account `owner@interview.local`. Without
`INTERVIEW_OWNER_PASSWORD` a random password is generated and printed to the server log once — a
known default is deliberately not used. Force a front-end rebuild with `./run.sh --build`.

## Docker

A self-contained image: the front end is built inside, only the database volume is exposed. No
node or python on the host.

```bash
docker compose up -d --build     # http://localhost:8000
docker compose logs -f           # logs
docker compose down              # stop (data stays in the volume)
docker compose down -v           # stop and drop the data
```

Credentials are `admin` / `admin`. Known credentials in `compose.yaml` are intentional: the owner
is seeded once and the volume is persistent, so random ones would mean "no way in after the first
start". Use your own with `INTERVIEW_OWNER_EMAIL=<login> INTERVIEW_OWNER_PASSWORD=<password>
docker compose up -d`; changing them on a running instance requires recreating the volume
(`docker compose down -v`).

If `:8000` is taken (say `./run.sh` already runs there), use
`INTERVIEW_PORT=8080 docker compose up -d`.

The layout inside the container mirrors the server one from `deploy/ladder.service`: code in `/app`,
content in `/app/content`, database in a named volume on `/data`. Rebuilding the image does not
touch the data, and `content/` can stay read-only — the back end never writes there (uploads are
parsed in a temp directory and stored in the database).

## Development mode (hot reload)

Two processes:

```bash
# terminal 1 — back end
cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# terminal 2 — front end (Vite proxies /api to :8000)
cd frontend && npm run dev      # http://localhost:5173
```

## Studying a track

**Open the board.** A track card on the home page opens the matrix. The layout is **swimlanes**: a
column per section with a coloured translucent background, questions ranked top to bottom by
difficulty (base → junior → middle → senior by default, the left axis). A section splits into
**sub-columns** through the `subblock` field. A card shows a short `title` and tags; the full text
opens in the drawer. There are no edges between questions — it is a board of cards grouped by
section and difficulty, not a dependency graph.

**Work through it.** Every card carries a status of its own — `known`, `review` or `unknown` — kept
per user in the database. Column and level counters, and the progress bar on the home page, count
the `known` ones.

- **Click a card** — opens the drawer and makes the card current.
- **HUD at the bottom** — current card, how much of the track is reviewed, the three status buttons
  and an optional timer.
- **Filters** — sections, difficulty, kind and tags, full-text search, and "unreviewed only", which
  dims everything already marked as known.
- **Keyboard:** `1 / 2 / 3` set the status of the current card and move to the next one, `↑↓` move by
  difficulty, `←→` between columns, `Enter` opens the drawer, `n` jumps to the next unreviewed card,
  `Esc` clears the current one, `?` shows the shortcut cheat sheet.

**Keep the bank fresh.** New questions are uploaded as `.md` / `.json`, written straight in the UI,
or added to `content/` and pulled in with "Update from files" (`POST /api/pools/sync`) without a
restart.

## Modes: demo and full access

The mode follows the session: no session — the demo, signed in — the full mode.

- **Demo, no sign-in.** `/` is a start screen with "Open demo" and the language switch. The demo home
  (`#/demo`) lists only the tracks marked `demo: true` — Data Engineer and System Analyst — in the
  language of the interface. Boards, filters, search and hotkeys work as usual; the checklist is kept in
  this browser's `localStorage` and nothing is written to the server. Editing is hidden (new track, the
  track menu, card edit and delete, adding and uploading questions).
  Any other track address leads back to `#/demo`.
- **Signing in.** The quiet "Sign in" link in the bottom corner of the start screen, or `#/login`.
- **Roles.** `owner` can do everything; `viewer` (invited people) reads every track and keeps a
  checklist of their own on the server; `member` can also edit content. Controls a role cannot use are
  not shown.
- **People (owner).** `#/people`: add an account by email — the server generates a one-time password
  and shows it once, pass it on; "Reset password" issues a new one and signs the user out everywhere;
  "Delete" removes the account together with its checklist.
- **Your password.** "Change password" in the account menu on the home page or in ⚙ on a board: the
  current one, a new one (at least 8 characters) and a repeat. Your other devices are signed out, the
  current session stays. "Sign out" sits next to it.

Without a session the API serves exactly two read endpoints — `GET /api/pools` (demo tracks, no
checklist summary) and `GET /api/graph?pool=<demo track>`; everything else answers 401.

## Content

Questions live in track pools: `content/<pool>/pool.yaml` describes the sections (column order,
labels, colours, sub-columns, weights) and the difficulty levels (`levels`, the matrix rows) and `content/<pool>/<block>/*.md|*.json` holds the questions
themselves. `pool.yaml` is the seed: at runtime tracks are read from the database, so they can be
created, edited and deleted from the UI (`POST/PUT/DELETE /api/pools`). A new track is either a copy
of an existing one (structure and questions included) or a structure you build yourself in the
editor.

Three optional `pool.yaml` keys drive the demo: `demo: true` makes a track readable without signing
in, `lang` is the content language (`ru` by default, or `en`), and `translation_of: <pool id>` marks a
translation. With the English interface the home page shows the translation instead of the original,
and the language switch on a board jumps to the paired track; checklists of the original and the
translation are separate. The keys are content properties: sync carries them over from the files,
tracks created in the UI are `demo: false`, `lang: ru`.

The repository ships several Russian-language tracks. `data-engineer` and `system-analyst` form the
demo and have full English translations — `data-engineer-en` and `system-analyst-en`, where a card id
is the original id plus `-en`. `demo/content-en` is a separate English set used for the screenshots
above.

### Markdown format

```markdown
---
id: spark-shuffle-01
kind: question            # question | task
block: frameworks         # one of blocks[].id in pool.yaml
difficulty: middle        # one of levels[].id in pool.yaml (base/junior/middle/senior when levels is omitted)
subblock: pyspark         # (optional) sub-column inside the section
title: Shuffle in Spark   # short heading shown on the card
topic: distributed-batch
difficulty: middle        # base | junior | middle | senior
weight: 13
tags: [optimization, distributed]
---
## Question
The question text…

## Answer
The answer (Markdown, code blocks supported)…
```

- **`title`** — the short heading on the card; the full text lives in the drawer.
- **`tags`** — rendered as chips on the card and available as filters. Keep to the ~17 cross-cutting
  concepts listed in `AGENTS.md`, one to three per card.
- `kind: task` adds `starterCode` and `rubric`, and the body may use `## Task` / `## Solution`.

> **Body parsing:** lines starting with `#` are treated as split markers between question and
> answer. If the answer needs a line starting with `#` outside a code block, set `question` /
> `answer` in the frontmatter directly — then the body is not parsed.

## API

| method              | path                               | purpose                                                                                                       |
|---------------------|------------------------------------|---------------------------------------------------------------------------------------------------------------|
| GET                 | `/api/pools`                       | tracks with sections, question counts and checklist summary; without a session — demo tracks only, no summary |
| POST                | `/api/pools`                       | create a track from a preset or from your own sections                                                        |
| PUT                 | `/api/pools/{id}`                  | rename a track or edit its sections and levels                                                                |
| POST                | `/api/pools/sync`                  | re-read `content/` into the database (owner)                                                                  |
| GET                 | `/api/graph?pool=<id>`             | nodes plus import errors; without a session — demo tracks only                                                |
| PUT                 | `/api/progress/{node_id}`          | set a card's status (`{status}`: known / review / unknown)                                                    |
| GET                 | `/api/progress?pool=<id>`          | the current user's checklist for a track                                                                      |
| POST                | `/api/auth/password`               | change your own password (wrong current one → 403, new one under 8 characters → 422)                          |
| GET                 | `/api/pools/{id}`                  | one track: sections, sub-columns, levels, counts                                                              |
| GET                 | `/api/nodes?pool=<id>&…`           | cards of a track, filtered by `block`, `subblock`, `difficulty`, `topic`, `tag`, `kind`, text `q`             |
| GET/POST/PUT/DELETE | `/api/nodes/{id}`                  | one card: every field, an explicit id on create, moves between tracks, sections and levels on update          |
| GET/PUT/DELETE      | `/api/pools/{id}/topics[/{topic}]` | topics of a track with counts; rename or delete a topic across its cards                                      |
| GET                 | `/api/tags[?pool=<id>]`            | the concept tag vocabulary and the tags a track already uses                                                  |

That is the core. The full list (import on `/api/import`, auth on `/api/auth/*`, accounts on
`/api/users` — create with a one-time password, reset, delete) and the schemas are in the Swagger UI
at `/docs`.

### MCP server

`tools/ladder-mcp` is an MCP server over this API: list and edit tracks, their sections and
sub-columns (vertical), levels (horizontal), topics and question cards — 24 tools, from
`get_direction` with a coverage matrix to `create_questions` in batches. It signs in as an account
that may edit content and runs over stdio against a local container or the live site. Setup,
the tool list and tests are in [tools/ladder-mcp/README.md](tools/ladder-mcp/README.md).

## Tests

Back end — 144 tests: content import, node CRUD, track CRUD with levels, `content/` sync with the
demo flags, the checklist, auth and RBAC with tenant isolation, anonymous demo access, passwords and
accounts.

```bash
cd backend && . .venv/bin/activate && pytest -q
```

Front end — a headless smoke test of the real runtime: the demo without signing in (start screen,
demo home, the checklist surviving a reload in the browser, the switch to the English translation),
signing in at `#/login`, the track wizard and structure editor, the matrix rendering, a card opening
the drawer, the checklist (including persistence across a reload), filters and search, the question
bank with upload, edit and export, and accounts (People, a viewer signing in read-only and changing the
password). It needs a running server on `:8000`, best on a fresh database (`INTERVIEW_DB_PATH`
pointing to a temporary file):

```bash
cd frontend && npm run build     # tsc --noEmit + vite build
npm run i18n:check               # every t("…") key exists in src/i18n/en.ts
npm run smoke
```

`frontend/shots.mjs` (the README screenshots) still drives the removed interview mode and is
currently out of date — see the note under the screenshots. Since the demo mode it also has to sign in
at `#/login`: `/` is the start screen now.

## Configuration (env)

- `INTERVIEW_CONTENT_DIR` — content directory (default `./content`)
- `INTERVIEW_DB_PATH` — SQLite path (default `backend/interview.db`); use an **absolute** path, the
  server starts from `backend/` and a relative one resolves against it
- `INTERVIEW_FRONTEND_DIR` — built front end (default `frontend/dist`)
- `INTERVIEW_OWNER_PASSWORD` — owner password on first start (random and logged otherwise)

## Deploy

Deploying to **https://ladder.paveldiordits.site** is a manual GitHub Actions run (*Deploy → Run workflow*);
merging into `main` deploys nothing. The front end is
built on the runner and shipped as one tarball to a forced-command SSH key on the server. Details and the
one-time server setup are in `DEPLOY.md`.

See `REPORT.md` for the design notes behind the architecture, and `AGENTS.md` for the repository
map and content conventions.
