"""
Verilənlər bazası - SQLite (inkişaf) / PostgreSQL (istehsal)
"""

import aiosqlite
import json
import os
from datetime import datetime

DB_PATH = "smeta_bot.db"


async def init_db():
    """Cədvəlləri yarat"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name        TEXT,
                phone       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS smetas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number    TEXT UNIQUE,
                client_id       INTEGER REFERENCES clients(id),
                telegram_id     INTEGER,
                client_name     TEXT,
                client_phone    TEXT,
                address         TEXT,
                rooms_data      TEXT,   -- JSON
                subtotal        REAL,
                margin_pct      REAL,
                discount_pct    REAL,
                vat_pct         REAL,
                total           REAL,
                notes           TEXT,
                status          TEXT DEFAULT 'draft',   -- draft / sent / approved / rejected
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_id        INTEGER REFERENCES smetas(id),
                name            TEXT,
                address         TEXT,
                start_date      TEXT,
                end_date        TEXT,
                status          TEXT DEFAULT 'active',  -- active / paused / done
                progress_pct    INTEGER DEFAULT 0,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS project_updates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER REFERENCES projects(id),
                message     TEXT,
                photo_ids   TEXT,   -- JSON list of Telegram file_ids
                created_by  INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.commit()


# ── Smeta funksiyaları ────────────────────────────────────────────────────────

async def save_smeta(data: dict) -> int:
    """Smeta saxla, ID qaytar"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO smetas
                (smeta_number, telegram_id, client_name, client_phone,
                 address, rooms_data, subtotal, margin_pct, discount_pct,
                 vat_pct, total, notes, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["smeta_number"],
            data["telegram_id"],
            data["client_name"],
            data["client_phone"],
            data["address"],
            json.dumps(data["rooms_data"], ensure_ascii=False),
            data["subtotal"],
            data["margin_pct"],
            data["discount_pct"],
            data["vat_pct"],
            data["total"],
            data.get("notes", ""),
            "draft",
        ))
        await db.commit()
        return cursor.lastrowid


async def get_smeta(smeta_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM smetas WHERE id=?", (smeta_id,)) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(row)
                d["rooms_data"] = json.loads(d["rooms_data"])
                return d
    return None


async def get_user_smetas(telegram_id: int, limit=10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, smeta_number, client_name, total, status, created_at "
            "FROM smetas WHERE telegram_id=? ORDER BY created_at DESC LIMIT ?",
            (telegram_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def update_smeta_status(smeta_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE smetas SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, smeta_id)
        )
        await db.commit()


async def generate_smeta_number() -> str:
    """SM-2025-0001 formatında nömrə"""
    year = datetime.now().year
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM smetas WHERE smeta_number LIKE ?",
            (f"SM-{year}-%",)
        ) as cur:
            count = (await cur.fetchone())[0]
    return f"SM-{year}-{count + 1:04d}"


# ── Layihə funksiyaları ───────────────────────────────────────────────────────

async def save_project(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO projects (smeta_id, name, address, start_date, end_date, notes)
            VALUES (?,?,?,?,?,?)
        """, (
            data.get("smeta_id"),
            data["name"],
            data["address"],
            data.get("start_date", ""),
            data.get("end_date", ""),
            data.get("notes", ""),
        ))
        await db.commit()
        return cursor.lastrowid


async def get_active_projects() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM projects WHERE status='active' ORDER BY created_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def update_project_progress(project_id: int, progress: int, notes: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET progress_pct=?, notes=? WHERE id=?",
            (progress, notes, project_id)
        )
        await db.commit()
