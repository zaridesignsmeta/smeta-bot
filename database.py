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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS room_progress (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_id    INTEGER REFERENCES smetas(id),
                smeta_number TEXT,
                room_name   TEXT,
                progress_pct INTEGER DEFAULT 0,
                notes       TEXT,
                updated_by  INTEGER,
                updated_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(smeta_number, room_name)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS smeta_photos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                room_name   TEXT,
                file_id     TEXT,
                caption     TEXT,
                uploaded_by INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                name         TEXT,
                unit         TEXT,
                qty_needed   REAL DEFAULT 0,
                qty_bought   REAL DEFAULT 0,
                price        REAL DEFAULT 0,
                status       TEXT DEFAULT 'pending',
                notes        TEXT,
                added_by     INTEGER,
                created_at   TEXT DEFAULT (datetime('now')),
                updated_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS checklist (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                room_name    TEXT,
                item         TEXT,
                is_checked   INTEGER DEFAULT 0,
                checked_by   INTEGER,
                checked_at   TEXT,
                notes        TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number    TEXT,
                amount          REAL,
                payment_type    TEXT,
                material_amount REAL DEFAULT 0,
                labor_amount    REAL DEFAULT 0,
                other_amount    REAL DEFAULT 0,
                notes           TEXT,
                created_by      INTEGER,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER DEFAULT 0,
                name        TEXT,
                phone       TEXT,
                role        TEXT,
                daily_rate  REAL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS worker_assignments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                worker_id    INTEGER REFERENCES workers(id),
                start_date   TEXT,
                end_date     TEXT,
                notes        TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS worker_payments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                worker_id    INTEGER REFERENCES workers(id),
                amount       REAL,
                date         TEXT,
                notes        TEXT,
                created_by   INTEGER,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                message      TEXT,
                remind_at    TEXT,
                is_sent      INTEGER DEFAULT 0,
                created_by   INTEGER,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                smeta_number TEXT,
                item_name    TEXT,
                unit         TEXT,
                qty          REAL DEFAULT 0,
                priority     TEXT DEFAULT 'normal',
                status       TEXT DEFAULT 'pending',
                price_paid   REAL DEFAULT 0,
                notes        TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS material_photos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id  INTEGER DEFAULT 0,
                smeta_number TEXT,
                file_id      TEXT,
                caption      TEXT,
                uploaded_by  INTEGER,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS smeta_groups (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id     INTEGER UNIQUE,
                smeta_number TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        # Add new columns to smetas if they don't exist yet
        for col_def in [
            "ALTER TABLE smetas ADD COLUMN object_type TEXT",
            "ALTER TABLE smetas ADD COLUMN price_category TEXT",
            "ALTER TABLE smetas ADD COLUMN area_m2 REAL",
            "ALTER TABLE smetas ADD COLUMN start_date TEXT",
            "ALTER TABLE smetas ADD COLUMN expected_end_date TEXT",
        ]:
            try:
                await db.execute(col_def)
            except Exception:
                pass  # column already exists

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
            data.get("subtotal", 0),
            data.get("margin_pct", 0),
            data.get("discount_pct", 0),
            0,
            data.get("total", 0),
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

# ── Otaq gedişat funksiyaları ─────────────────────────────────────────────────

async def update_room_progress(smeta_number: str, room_name: str, progress: int, notes: str = "", user_id: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO room_progress (smeta_number, room_name, progress_pct, notes, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(smeta_number, room_name)
            DO UPDATE SET progress_pct=excluded.progress_pct, notes=excluded.notes,
                          updated_by=excluded.updated_by, updated_at=excluded.updated_at
        """, (smeta_number, room_name, progress, notes, user_id))
        await db.commit()

async def get_room_progress(smeta_number: str) -> dict:
    """Smeta üzrə bütün otaqların gedişatı — {room_name: {progress_pct, notes, updated_at}}"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM room_progress WHERE smeta_number=?", (smeta_number,)
        ) as cur:
            rows = await cur.fetchall()
            return {r["room_name"]: dict(r) for r in rows}

async def save_photo(smeta_number: str, room_name: str, file_id: str, caption: str = "", user_id: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO smeta_photos (smeta_number, room_name, file_id, caption, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (smeta_number, room_name, file_id, caption, user_id))
        await db.commit()

async def get_photos(smeta_number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM smeta_photos WHERE smeta_number=? ORDER BY created_at DESC",
            (smeta_number,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def get_smeta_by_number(smeta_number: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM smetas WHERE smeta_number=?", (smeta_number,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(row)
                d["rooms_data"] = json.loads(d["rooms_data"])
                return d
            return None

async def get_user_smeta_numbers(telegram_id: int) -> list:
    """İstifadəçinin son smetalarının nömrələri"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT smeta_number, client_name, address FROM smetas WHERE telegram_id=? ORDER BY created_at DESC LIMIT 20",
            (telegram_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

# ── Qrup funksiyaları ─────────────────────────────────────────────────────────

async def link_group_to_smeta(group_id: int, smeta_number: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS smeta_groups (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id     INTEGER UNIQUE,
                smeta_number TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            INSERT OR REPLACE INTO smeta_groups (group_id, smeta_number)
            VALUES (?, ?)
        """, (group_id, smeta_number))
        await db.commit()

async def get_smeta_by_group(group_id: int) -> str | None:
    """Qrup ID-sinə görə smeta nömrəsini tap"""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute(
                "SELECT smeta_number FROM smeta_groups WHERE group_id=?", (group_id,)
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None

async def get_group_by_smeta(smeta_number: str) -> int | None:
    """Smeta nömrəsinə görə qrup ID-sini tap"""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            async with db.execute(
                "SELECT group_id FROM smeta_groups WHERE smeta_number=?", (smeta_number,)
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None

# ── Material funksiyaları ─────────────────────────────────────────────────────

async def add_material(smeta_number: str, name: str, unit: str, qty_needed: float, price: float, user_id: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO materials (smeta_number, name, unit, qty_needed, price, status, added_by)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (smeta_number, name, unit, qty_needed, price, user_id))
        await db.commit()
        return cursor.lastrowid

async def update_material_status(material_id: int, qty_bought: float, status: str, notes: str = ""):
    """status: pending / bought / delivered"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE materials SET qty_bought=?, status=?, notes=?, updated_at=datetime('now')
            WHERE id=?
        """, (qty_bought, status, notes, material_id))
        await db.commit()

async def get_materials(smeta_number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM materials WHERE smeta_number=? ORDER BY created_at",
            (smeta_number,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

# ── Check-list funksiyaları ───────────────────────────────────────────────────

async def add_checklist_item(smeta_number: str, room_name: str, item: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO checklist (smeta_number, room_name, item)
            VALUES (?, ?, ?)
        """, (smeta_number, room_name, item))
        await db.commit()
        return cursor.lastrowid

async def check_item(item_id: int, user_id: int, notes: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE checklist SET is_checked=1, checked_by=?, checked_at=datetime('now'), notes=?
            WHERE id=?
        """, (user_id, notes, item_id))
        await db.commit()

async def uncheck_item(item_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE checklist SET is_checked=0, checked_by=NULL, checked_at=NULL WHERE id=?",
            (item_id,)
        )
        await db.commit()

async def get_checklist(smeta_number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM checklist WHERE smeta_number=? ORDER BY room_name, created_at",
            (smeta_number,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def init_checklist_for_smeta(smeta_number: str, rooms: list):
    """Smeta yarananda standart check-list maddələri əlavə et"""
    standard_items = [
        "Suvaq işləri yoxlanıldı",
        "Şpatlevka hamar çıxdı",
        "Boya bərabər vuruldu",
        "Elektrik xətləri test edildi",
        "Rozetka/açarlar işləyir",
        "Santexnika sızdırmırdır",
        "Döşəmə düz döşəndi",
        "Tavan işləri tamamlandı",
        "Kafel/keramogranit düzgün yapışdırıldı",
        "Qapı açılışları düzgündür",
        "Pəncərə kənarları hamar çıxdı",
        "Ümumi təmizlik edildi",
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        for room in rooms:
            for item in standard_items:
                await db.execute("""
                    INSERT OR IGNORE INTO checklist (smeta_number, room_name, item)
                    VALUES (?, ?, ?)
                """, (smeta_number, room, item))
        await db.commit()


# ── Ödəniş funksiyaları ───────────────────────────────────────────────────────

async def add_payment(smeta_number: str, amount: float, payment_type: str,
                      material_amount: float = 0, labor_amount: float = 0,
                      other_amount: float = 0, notes: str = "", created_by: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO payments (smeta_number, amount, payment_type, material_amount,
                                  labor_amount, other_amount, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (smeta_number, amount, payment_type, material_amount,
              labor_amount, other_amount, notes, created_by))
        await db.commit()
        return cursor.lastrowid


async def get_payments(smeta_number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE smeta_number=? ORDER BY created_at",
            (smeta_number,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_total_paid(smeta_number: str) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE smeta_number=?",
            (smeta_number,)
        ) as cur:
            return (await cur.fetchone())[0]


# ── İşçi funksiyaları ─────────────────────────────────────────────────────────

async def add_worker(telegram_id: int, name: str, phone: str, role: str, daily_rate: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO workers (telegram_id, name, phone, role, daily_rate)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, name, phone, role, daily_rate))
        await db.commit()
        return cursor.lastrowid


async def get_workers() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM workers ORDER BY name") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_worker(worker_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM workers WHERE id=?", (worker_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def assign_worker(smeta_number: str, worker_id: int, start_date: str,
                        end_date: str = "", notes: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO worker_assignments (smeta_number, worker_id, start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (smeta_number, worker_id, start_date, end_date, notes))
        await db.commit()
        return cursor.lastrowid


async def get_worker_assignments(smeta_number: str = None, worker_id: int = None) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if smeta_number:
            async with db.execute("""
                SELECT wa.*, w.name, w.role, w.phone, w.daily_rate
                FROM worker_assignments wa
                JOIN workers w ON w.id = wa.worker_id
                WHERE wa.smeta_number=?
            """, (smeta_number,)) as cur:
                return [dict(r) for r in await cur.fetchall()]
        elif worker_id:
            async with db.execute(
                "SELECT * FROM worker_assignments WHERE worker_id=? ORDER BY start_date DESC",
                (worker_id,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        return []


async def add_worker_payment(smeta_number: str, worker_id: int, amount: float,
                             date: str, notes: str = "", created_by: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO worker_payments (smeta_number, worker_id, amount, date, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (smeta_number, worker_id, amount, date, notes, created_by))
        await db.commit()
        return cursor.lastrowid


async def get_worker_payments_by_month(worker_id: int, month: str) -> list:
    """month = '2026-03' format"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT wp.*, w.name as worker_name, w.role
            FROM worker_payments wp
            JOIN workers w ON w.id = wp.worker_id
            WHERE wp.worker_id=? AND strftime('%Y-%m', wp.created_at)=?
            ORDER BY wp.created_at DESC
        """, (worker_id, month)) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Xatırlatma funksiyaları ───────────────────────────────────────────────────

async def add_reminder(smeta_number: str, message: str, remind_at: str, created_by: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO reminders (smeta_number, message, remind_at, created_by)
            VALUES (?, ?, ?, ?)
        """, (smeta_number, message, remind_at, created_by))
        await db.commit()
        return cursor.lastrowid


async def get_pending_reminders() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM reminders
            WHERE is_sent=0 AND remind_at <= datetime('now')
            ORDER BY remind_at
        """) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def mark_reminder_sent(reminder_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET is_sent=1 WHERE id=?", (reminder_id,))
        await db.commit()


# ── Alış siyahısı funksiyaları ────────────────────────────────────────────────

async def add_shopping_item(smeta_number: str, item_name: str, unit: str,
                            qty: float, priority: str = "normal", notes: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO shopping_list (smeta_number, item_name, unit, qty, priority, status, notes)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (smeta_number, item_name, unit, qty, priority, notes))
        await db.commit()
        return cursor.lastrowid


async def get_shopping_list(smeta_number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM shopping_list WHERE smeta_number=? ORDER BY priority, created_at",
            (smeta_number,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def update_shopping_item(item_id: int, status: str, price_paid: float = 0, notes: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE shopping_list SET status=?, price_paid=?, notes=?
            WHERE id=?
        """, (status, price_paid, notes, item_id))
        await db.commit()


# ── Material foto ─────────────────────────────────────────────────────────────

async def save_material_photo(material_id: int, smeta_number: str, file_id: str,
                              caption: str = "", uploaded_by: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO material_photos (material_id, smeta_number, file_id, caption, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (material_id, smeta_number, file_id, caption, uploaded_by))
        await db.commit()


async def get_material_photos(smeta_number: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM material_photos WHERE smeta_number=? ORDER BY created_at DESC",
            (smeta_number,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Aylıq hesabat ─────────────────────────────────────────────────────────────

async def get_monthly_report(month: str) -> dict:
    """month = '2026-03' formatında"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total_value
            FROM smetas WHERE strftime('%Y-%m', created_at)=?
        """, (month,)) as cur:
            row = dict(await cur.fetchone())
            new_smetas = row["count"]
            total_value = row["total_value"]

        async with db.execute("""
            SELECT COUNT(*) as count FROM smetas
            WHERE status='approved' AND strftime('%Y-%m', updated_at)=?
        """, (month,)) as cur:
            completed = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) as count FROM smetas WHERE status='active'"
        ) as cur:
            active = (await cur.fetchone())[0]

        async with db.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM payments WHERE strftime('%Y-%m', created_at)=?
        """, (month,)) as cur:
            received_payments = (await cur.fetchone())[0]

        async with db.execute("""
            SELECT COALESCE(SUM(price_paid), 0) as total
            FROM shopping_list WHERE status='bought' AND strftime('%Y-%m', created_at)=?
        """, (month,)) as cur:
            material_costs = (await cur.fetchone())[0]

        async with db.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM worker_payments WHERE strftime('%Y-%m', created_at)=?
        """, (month,)) as cur:
            worker_costs = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COALESCE(SUM(total), 0) FROM smetas WHERE status='approved'"
        ) as cur:
            total_approved = (await cur.fetchone())[0]

        async with db.execute("SELECT COALESCE(SUM(amount), 0) FROM payments") as cur:
            total_received_all = (await cur.fetchone())[0]

        expected_payments = max(0, total_approved - total_received_all)
        profit = received_payments - material_costs - worker_costs

        return {
            "month": month,
            "new_smetas": new_smetas,
            "completed": completed,
            "active": active,
            "total_value": total_value,
            "received_payments": received_payments,
            "expected_payments": expected_payments,
            "material_costs": material_costs,
            "worker_costs": worker_costs,
            "profit": profit,
        }


async def get_all_smetas_for_report(month: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT s.smeta_number, s.client_name, s.total, s.status, s.created_at,
                   COALESCE((SELECT SUM(p.amount) FROM payments p
                             WHERE p.smeta_number=s.smeta_number), 0) as paid
            FROM smetas s
            WHERE strftime('%Y-%m', s.created_at)=?
            ORDER BY s.created_at
        """, (month,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_smetas_admin() -> list:
    """Admin üçün bütün smetalar"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, smeta_number, client_name, total, status, created_at, telegram_id "
            "FROM smetas ORDER BY created_at DESC LIMIT 50"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
