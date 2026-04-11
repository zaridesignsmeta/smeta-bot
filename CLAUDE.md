# CLAUDE.md — smeta-bot Codebase Guide

This document is written for AI assistants (Claude Code and similar) working on this repository. It covers architecture, conventions, and development workflows.

---

## Overview

**smeta-bot** is a Telegram bot for Azerbaijani interior design companies (currently branded for "Zari Design"). It automates the full workflow from generating cost estimates (smeta) to project management, payments, and reporting. It also includes a Flask-based web dashboard for viewing data.

- **Language:** Python 3.12
- **Bot Framework:** aiogram 3.7.0 (async, FSM-based)
- **Database:** PostgreSQL via asyncpg (hosted on Railway)
- **AI Integration:** Claude API (`claude-opus-4-6`) for Smart Smeta feature
- **Web Dashboard:** Flask 3.0.3, running on port 8080
- **Deployment:** Railway.app via `nixpacks.toml`
- **UI Language:** Azerbaijani throughout (variable names, comments, button text)

---

## Repository Structure

```
smeta-bot/
├── bot.py                   # Entry point — starts bot + Flask + background tasks
├── config.py                # All configuration, constants, pricing, room definitions
├── database.py              # Full PostgreSQL ORM layer (asyncpg pool)
├── generators.py            # Excel (openpyxl) and PDF (reportlab) file generation
├── handlers.py              # Main Telegram handlers; FSM smeta creation flow (2183 lines)
├── handlers_material.py     # Shopping list / material tracking feature
├── handlers_payment.py      # Payment recording and history feature
├── handlers_project.py      # Project lifecycle management feature
├── handlers_reminder.py     # Reminder / scheduled notification feature
├── handlers_report.py       # Monthly financial reports feature
├── handlers_smart_smeta.py  # Claude AI-powered "Smart Smeta" feature
├── handlers_worker.py       # Worker management and assignment feature
├── web.py                   # Flask web dashboard
├── requirements.txt         # Python dependencies
├── runtime.txt              # Python 3.12.0
├── nixpacks.toml            # Railway build configuration
├── README.md                # Setup guide (written in Azerbaijani)
└── assetslogo.png           # Company logo used in generated documents
```

There is no `src/` subdirectory — all Python modules live at the root.

---

## Application Startup (`bot.py`)

The startup sequence:
1. Load `.env` via `python-dotenv`
2. Initialize the PostgreSQL connection pool (`database.init_db()`)
3. Create all DB tables if they don't exist
4. Start Flask web server in a background thread on `PORT` (default 8080)
5. Register all routers (main + feature sub-routers)
6. Launch `check_reminders()` as an asyncio background task (runs every 3600s)
7. Start aiogram polling

The bot and Flask share the same database pool.

---

## Configuration (`config.py`)

All runtime config comes from environment variables. Key variables:

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `ADMIN_IDS` | Comma-separated Telegram user IDs with admin privileges |
| `DATABASE_URL` | PostgreSQL connection string (Railway format auto-converted to asyncpg format) |
| `ANTHROPIC_API_KEY` | Claude API key for Smart Smeta |
| `AI_MODEL` | Claude model ID (default: `claude-opus-4-6`) |
| `PORT` | Flask port (default: 8080) |

Hard-coded business constants (edit in `config.py`):
- `COMPANY_NAME`, `COMPANY_PHONE`, `COMPANY_EMAIL`, `COMPANY_ADDRESS`
- `CURRENCY = "AZN"`
- `DEFAULT_MARGIN = 20` (percentage markup)
- Price tiers: Standart 250, Orta 350, Premium 500 AZN/m²

---

## Database Layer (`database.py`)

### Connection

Uses `asyncpg` connection pool. Initialized once at startup, shared across all modules as a module-level global `pool`.

### Tables

| Table | Purpose |
|---|---|
| `clients` | Telegram user profiles |
| `smetas` | Cost estimates (central entity) |
| `projects` | Projects linked to smetas |
| `project_updates` | Photo/status updates on projects |
| `room_progress` | Per-room progress percentages |
| `smeta_photos` | Photos attached to smetas |
| `materials` | Material items per smeta |
| `checklist` | Task checklists per room |
| `payments` | Payment records |
| `workers` | Worker profiles |
| `worker_assignments` | Worker ↔ smeta assignments |
| `worker_payments` | Salary payments to workers |
| `reminders` | Scheduled notifications |
| `shopping_list` | Shopping list items per smeta |
| `material_photos` | Reference photos for materials |
| `smeta_groups` | Linked Telegram group IDs |

### Key Relationships

```
clients (1) ──→ (many) smetas
smetas  (1) ──→ (many) projects
smetas  (1) ──→ (many) payments
smetas  (1) ──→ (many) materials / shopping_list
smetas  (1) ──→ (many) room_progress
workers (many) ←→ (many) smetas  [via worker_assignments]
```

### Conventions

- Timestamps: `TIMESTAMPTZ`
- JSON blobs (e.g., `rooms_data`, `flooring_data`, `special_rooms`): stored as `TEXT`, serialized/deserialized by the application layer
- Currency values: `FLOAT`
- Percentages and progress: `INTEGER`
- No ORM (SQLAlchemy etc.) — raw asyncpg queries

---

## Handlers Architecture

All Telegram handlers use **aiogram 3 routers**. Each feature has its own router in a dedicated file. Routers are registered in `handlers.py`:

```python
router.include_router(smart_smeta_router)
router.include_router(payment_router)
router.include_router(worker_router)
router.include_router(project_router)
router.include_router(reminder_router)
router.include_router(material_router)
router.include_router(report_router)
```

The main `router` from `handlers.py` is registered in `bot.py`.

### FSM (Finite State Machine) Pattern

Multi-step workflows use aiogram's `StatesGroup`:

```python
class SmetaForm(StatesGroup):
    object_type = State()
    price_category = State()
    area_m2 = State()
    # ...
```

State transitions are triggered by inline keyboard callbacks. Always clear state with `await state.clear()` at the terminal step.

### Callback Data Conventions

Callbacks use string prefixes to route to the correct handler:

| Prefix | Feature |
|---|---|
| `smeta_` | Smeta operations |
| `room_` | Room selection |
| `obj_` | Object type selection |
| `price_` | Price category |
| `pay_` | Payment operations |
| `work_` | Worker management |
| `proj_` | Project management |
| `mat_` | Material tracking |
| `smart_` | Smart Smeta flow |

### Keyboard Builders

Keyboards are pure functions returning `InlineKeyboardMarkup` or `ReplyKeyboardMarkup`. Naming convention: `<feature>_kb()`. Keep them pure — no side effects.

---

## Smart Smeta Feature (`handlers_smart_smeta.py`)

This feature replaces the 40+ step manual smeta creation with 7 user inputs. It calls the Claude API to compute all pricing automatically.

**Flow:**
1. User provides: object type, area, room config (e.g. "2+1"), price tier, flooring type, special rooms, discount
2. App sends structured prompt to Claude API
3. Claude returns JSON with full pricing breakdown
4. JSON is parsed and saved to the database exactly like a manual smeta

**Room config notation:** `"2+1"` means 2 bedrooms + 1 living room. Special rooms (garage, server room, laundry, technical room) are handled separately.

**Model used:** `config.AI_MODEL` (currently `claude-opus-4-6`)

When modifying this feature, ensure the Claude API prompt returns valid JSON matching the expected schema before saving to the database.

---

## File Generation (`generators.py`)

Two output formats:

- **Excel** (`.xlsx`) — generated with `openpyxl`
- **PDF** — generated with `reportlab`

Both use:
- Company branding from `config.py` and `assetslogo.png`
- Color scheme: Dark blue `#1B2A4A`, Gold `#C9973A`
- Azerbaijani character support (ensure fonts support it)
- Output directory: `output/` (created automatically if missing)

Generated files are sent to the user via Telegram then can be cleaned up.

---

## Web Dashboard (`web.py`)

Flask application with server-side rendered HTML (no separate frontend framework). Serves:
- Overview tab (smeta summary, financial totals)
- Progress tab (room-by-room status)
- Materials tab (shopping list)
- Checklist tab (task list)
- Photo gallery

The dashboard shares the asyncpg pool using `asyncio.run()` wrappers to call async DB functions from sync Flask routes.

---

## Development Workflow

### Local Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd smeta-bot

# 2. Create virtualenv
python3.12 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env   # (no .env.example exists — create .env manually)
# Required: BOT_TOKEN, DATABASE_URL, ANTHROPIC_API_KEY, ADMIN_IDS

# 5. Run
python bot.py
```

### Required `.env` Contents

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://user:pass@host:5432/dbname
ANTHROPIC_API_KEY=your_anthropic_key
ADMIN_IDS=123456789,987654321
PORT=8080
```

### Deployment (Railway)

Push to `main`. Railway uses `nixpacks.toml` to build and run `python bot.py`. Environment variables are set in the Railway dashboard. The `DATABASE_URL` from Railway uses the `postgres://` prefix — `database.py` auto-converts this to `postgresql://` for asyncpg.

---

## Branch Strategy

Feature branches follow the pattern: `claude/<feature-name>-<ID>`

- Always develop on a feature branch
- Merge to `main` via pull request
- The AI assistant's working branch for this session: `claude/add-claude-documentation-EUTCV`

---

## No Test Suite

There are currently **no automated tests**. All validation is:
- Input validation in handlers (via aiogram message filters)
- Manual testing via the Telegram bot interface

When adding tests in future, use `pytest` with `pytest-asyncio` for async database and handler tests.

---

## Key Conventions

1. **Language:** All user-facing strings, variable names, and comments are in Azerbaijani. Keep this consistent.

2. **Async everywhere:** All database calls are `async`. Never call them from sync context except in `web.py` (which wraps them with `asyncio.run()`).

3. **No ORM:** Write raw SQL using asyncpg. Use `$1, $2` parameter style (not `%s`).

4. **JSON as TEXT:** Complex nested data (room configs, flooring selections) is JSON-stringified before storing and parsed after fetching.

5. **Admin checks:** Features that modify data (payments, workers, etc.) check `user_id in config.ADMIN_IDS` before proceeding.

6. **Router isolation:** Each feature's handlers live in their own file with their own router. Don't add feature-specific handlers to `handlers.py` unless they belong to the core smeta flow.

7. **File cleanup:** Generated Excel/PDF files in `output/` should be deleted after being sent to the user.

8. **Callback prefixes:** Always use a unique prefix for a feature's callbacks to avoid routing conflicts.

9. **State clearing:** Always call `await state.clear()` at the end of FSM flows to prevent state leaks.

---

## Common Tasks

### Adding a new feature handler

1. Create `handlers_<feature>.py`
2. Define a new `Router`: `<feature>_router = Router()`
3. Add handlers using `@<feature>_router.message()` or `@<feature>_router.callback_query()`
4. Import and register in `handlers.py`: `router.include_router(<feature>_router)`

### Adding a new database table

1. Add `CREATE TABLE IF NOT EXISTS` statement in `database.py`'s `init_db()` function
2. Add CRUD functions in `database.py`
3. Import and use in the relevant handler file

### Modifying the Smart Smeta AI prompt

The prompt is constructed in `handlers_smart_smeta.py`. The Claude API response must be valid JSON. Always test that the JSON schema matches what the database insertion expects.

### Updating pricing or room types

All pricing constants and room type definitions live in `config.py`. Edit them there — they are imported everywhere else.
