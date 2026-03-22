"""
Verilənlər bazası - PostgreSQL (Railway)
"""

import asyncpg
import json
import os
from datetime import datetime

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL mühit dəyişəni təyin edilməyib")
        _pool = await asyncpg.create_pool(dsn)
    return _pool


async def init_db():
    """Cədvəlləri yarat"""
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id          SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                name        TEXT,
                phone       TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS smetas (
                id                SERIAL PRIMARY KEY,
                smeta_number      TEXT UNIQUE,
                client_id         INTEGER REFERENCES clients(id),
                telegram_id       BIGINT,
                client_name       TEXT,
                client_phone      TEXT,
                address           TEXT,
                rooms_data        TEXT,
                subtotal          FLOAT,
                margin_pct        FLOAT,
                discount_pct      FLOAT,
                vat_pct           FLOAT,
                total             FLOAT,
                notes             TEXT,
                status            TEXT DEFAULT 'draft',
                created_at        TIMESTAMPTZ DEFAULT NOW(),
                updated_at        TIMESTAMPTZ DEFAULT NOW(),
                object_type       TEXT,
                price_category    TEXT,
                area_m2           FLOAT,
                start_date        TEXT,
                expected_end_date TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id           SERIAL PRIMARY KEY,
                smeta_id     INTEGER REFERENCES smetas(id),
                name         TEXT,
                address      TEXT,
                start_date   TEXT,
                end_date     TEXT,
                status       TEXT DEFAULT 'active',
                progress_pct INTEGER DEFAULT 0,
                notes        TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS project_updates (
                id         SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id),
                message    TEXT,
                photo_ids  TEXT,
                created_by BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS room_progress (
                id           SERIAL PRIMARY KEY,
                smeta_id     INTEGER REFERENCES smetas(id),
                smeta_number TEXT,
                room_name    TEXT,
                progress_pct INTEGER DEFAULT 0,
                notes        TEXT,
                updated_by   BIGINT,
                updated_at   TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(smeta_number, room_name)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS smeta_photos (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                room_name    TEXT,
                file_id      TEXT,
                caption      TEXT,
                uploaded_by  BIGINT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                name         TEXT,
                unit         TEXT,
                qty_needed   FLOAT DEFAULT 0,
                qty_bought   FLOAT DEFAULT 0,
                price        FLOAT DEFAULT 0,
                status       TEXT DEFAULT 'pending',
                notes        TEXT,
                added_by     BIGINT,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                updated_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS checklist (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                room_name    TEXT,
                item         TEXT,
                is_checked   INTEGER DEFAULT 0,
                checked_by   BIGINT,
                checked_at   TIMESTAMPTZ,
                notes        TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(smeta_number, room_name, item)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id              SERIAL PRIMARY KEY,
                smeta_number    TEXT,
                amount          FLOAT,
                payment_type    TEXT,
                material_amount FLOAT DEFAULT 0,
                labor_amount    FLOAT DEFAULT 0,
                other_amount    FLOAT DEFAULT 0,
                notes           TEXT,
                created_by      BIGINT,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id          SERIAL PRIMARY KEY,
                telegram_id BIGINT DEFAULT 0,
                name        TEXT,
                phone       TEXT,
                role        TEXT,
                daily_rate  FLOAT DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS worker_assignments (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                worker_id    INTEGER REFERENCES workers(id),
                start_date   TEXT,
                end_date     TEXT,
                notes        TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS worker_payments (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                worker_id    INTEGER REFERENCES workers(id),
                amount       FLOAT,
                date         TEXT,
                notes        TEXT,
                created_by   BIGINT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                message      TEXT,
                remind_at    TEXT,
                is_sent      INTEGER DEFAULT 0,
                created_by   BIGINT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id           SERIAL PRIMARY KEY,
                smeta_number TEXT,
                item_name    TEXT,
                unit         TEXT,
                qty          FLOAT DEFAULT 0,
                priority     TEXT DEFAULT 'normal',
                status       TEXT DEFAULT 'pending',
                price_paid   FLOAT DEFAULT 0,
                notes        TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS material_photos (
                id           SERIAL PRIMARY KEY,
                material_id  INTEGER DEFAULT 0,
                smeta_number TEXT,
                file_id      TEXT,
                caption      TEXT,
                uploaded_by  BIGINT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS smeta_groups (
                id           SERIAL PRIMARY KEY,
                group_id     BIGINT UNIQUE,
                smeta_number TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)


# ── Smeta funksiyaları ────────────────────────────────────────────────────────

async def save_smeta(data: dict) -> int:
    """Smeta saxla, ID qaytar"""
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO smetas
            (smeta_number, telegram_id, client_name, client_phone,
             address, rooms_data, subtotal, margin_pct, discount_pct,
             vat_pct, total, notes, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        RETURNING id
    """,
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
    )


async def get_smeta(smeta_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM smetas WHERE id=$1", smeta_id)
    if row:
        d = dict(row)
        d["rooms_data"] = json.loads(d["rooms_data"])
        return d
    return None


async def get_user_smetas(telegram_id: int, limit=10) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, smeta_number, client_name, total, status, created_at "
        "FROM smetas WHERE telegram_id=$1 ORDER BY created_at DESC LIMIT $2",
        telegram_id, limit
    )
    return [dict(r) for r in rows]


async def update_smeta_status(smeta_id: int, status: str):
    pool = await get_pool()
    await pool.execute(
        "UPDATE smetas SET status=$1, updated_at=NOW() WHERE id=$2",
        status, smeta_id
    )


async def generate_smeta_number() -> str:
    """SM-2025-0001 formatında nömrə"""
    year = datetime.now().year
    pool = await get_pool()
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM smetas WHERE smeta_number LIKE $1",
        f"SM-{year}-%"
    )
    return f"SM-{year}-{count + 1:04d}"


# ── Layihə funksiyaları ───────────────────────────────────────────────────────

async def save_project(data: dict) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO projects (smeta_id, name, address, start_date, end_date, notes)
        VALUES ($1,$2,$3,$4,$5,$6)
        RETURNING id
    """,
        data.get("smeta_id"),
        data["name"],
        data["address"],
        data.get("start_date", ""),
        data.get("end_date", ""),
        data.get("notes", ""),
    )


async def get_active_projects() -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM projects WHERE status='active' ORDER BY created_at DESC"
    )
    return [dict(r) for r in rows]


async def update_project_progress(project_id: int, progress: int, notes: str = ""):
    pool = await get_pool()
    await pool.execute(
        "UPDATE projects SET progress_pct=$1, notes=$2 WHERE id=$3",
        progress, notes, project_id
    )


# ── Otaq gedişat funksiyaları ─────────────────────────────────────────────────

async def update_room_progress(smeta_number: str, room_name: str, progress: int,
                               notes: str = "", user_id: int = 0):
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO room_progress (smeta_number, room_name, progress_pct, notes, updated_by, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT(smeta_number, room_name)
        DO UPDATE SET progress_pct=EXCLUDED.progress_pct, notes=EXCLUDED.notes,
                      updated_by=EXCLUDED.updated_by, updated_at=NOW()
    """, smeta_number, room_name, progress, notes, user_id)


async def get_room_progress(smeta_number: str) -> dict:
    """Smeta üzrə bütün otaqların gedişatı — {room_name: {progress_pct, notes, updated_at}}"""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM room_progress WHERE smeta_number=$1", smeta_number
    )
    return {r["room_name"]: dict(r) for r in rows}


async def save_photo(smeta_number: str, room_name: str, file_id: str,
                     caption: str = "", user_id: int = 0):
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO smeta_photos (smeta_number, room_name, file_id, caption, uploaded_by)
        VALUES ($1, $2, $3, $4, $5)
    """, smeta_number, room_name, file_id, caption, user_id)


async def get_photos(smeta_number: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM smeta_photos WHERE smeta_number=$1 ORDER BY created_at DESC",
        smeta_number
    )
    return [dict(r) for r in rows]


async def get_smeta_by_number(smeta_number: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM smetas WHERE smeta_number=$1", smeta_number
    )
    if row:
        d = dict(row)
        d["rooms_data"] = json.loads(d["rooms_data"])
        return d
    return None


async def get_user_smeta_numbers(telegram_id: int) -> list:
    """İstifadəçinin son smetalarının nömrələri"""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT smeta_number, client_name, address FROM smetas "
        "WHERE telegram_id=$1 ORDER BY created_at DESC LIMIT 20",
        telegram_id
    )
    return [dict(r) for r in rows]


# ── Qrup funksiyaları ─────────────────────────────────────────────────────────

async def link_group_to_smeta(group_id: int, smeta_number: str):
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO smeta_groups (group_id, smeta_number)
        VALUES ($1, $2)
        ON CONFLICT(group_id) DO UPDATE SET smeta_number=EXCLUDED.smeta_number
    """, group_id, smeta_number)


async def get_smeta_by_group(group_id: int) -> str | None:
    """Qrup ID-sinə görə smeta nömrəsini tap"""
    pool = await get_pool()
    try:
        return await pool.fetchval(
            "SELECT smeta_number FROM smeta_groups WHERE group_id=$1", group_id
        )
    except Exception:
        return None


async def get_group_by_smeta(smeta_number: str) -> int | None:
    """Smeta nömrəsinə görə qrup ID-sini tap"""
    pool = await get_pool()
    try:
        return await pool.fetchval(
            "SELECT group_id FROM smeta_groups WHERE smeta_number=$1", smeta_number
        )
    except Exception:
        return None


# ── Material funksiyaları ─────────────────────────────────────────────────────

async def add_material(smeta_number: str, name: str, unit: str,
                       qty_needed: float, price: float, user_id: int = 0) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO materials (smeta_number, name, unit, qty_needed, price, status, added_by)
        VALUES ($1, $2, $3, $4, $5, 'pending', $6)
        RETURNING id
    """, smeta_number, name, unit, qty_needed, price, user_id)


async def update_material_status(material_id: int, qty_bought: float,
                                 status: str, notes: str = ""):
    """status: pending / bought / delivered"""
    pool = await get_pool()
    await pool.execute("""
        UPDATE materials SET qty_bought=$1, status=$2, notes=$3, updated_at=NOW()
        WHERE id=$4
    """, qty_bought, status, notes, material_id)


async def get_materials(smeta_number: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM materials WHERE smeta_number=$1 ORDER BY created_at",
        smeta_number
    )
    return [dict(r) for r in rows]


# ── Check-list funksiyaları ───────────────────────────────────────────────────

async def add_checklist_item(smeta_number: str, room_name: str, item: str) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO checklist (smeta_number, room_name, item)
        VALUES ($1, $2, $3)
        RETURNING id
    """, smeta_number, room_name, item)


async def check_item(item_id: int, user_id: int, notes: str = ""):
    pool = await get_pool()
    await pool.execute("""
        UPDATE checklist SET is_checked=1, checked_by=$1, checked_at=NOW(), notes=$2
        WHERE id=$3
    """, user_id, notes, item_id)


async def uncheck_item(item_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE checklist SET is_checked=0, checked_by=NULL, checked_at=NULL WHERE id=$1",
        item_id
    )


async def get_checklist(smeta_number: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM checklist WHERE smeta_number=$1 ORDER BY room_name, created_at",
        smeta_number
    )
    return [dict(r) for r in rows]


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
    pool = await get_pool()
    async with pool.acquire() as db:
        for room in rooms:
            for item in standard_items:
                await db.execute("""
                    INSERT INTO checklist (smeta_number, room_name, item)
                    VALUES ($1, $2, $3)
                    ON CONFLICT(smeta_number, room_name, item) DO NOTHING
                """, smeta_number, room, item)


# ── Ödəniş funksiyaları ───────────────────────────────────────────────────────

async def add_payment(smeta_number: str, amount: float, payment_type: str,
                      material_amount: float = 0, labor_amount: float = 0,
                      other_amount: float = 0, notes: str = "",
                      created_by: int = 0) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO payments (smeta_number, amount, payment_type, material_amount,
                              labor_amount, other_amount, notes, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """, smeta_number, amount, payment_type, material_amount,
        labor_amount, other_amount, notes, created_by)


async def get_payments(smeta_number: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM payments WHERE smeta_number=$1 ORDER BY created_at",
        smeta_number
    )
    return [dict(r) for r in rows]


async def get_total_paid(smeta_number: str) -> float:
    pool = await get_pool()
    val = await pool.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE smeta_number=$1",
        smeta_number
    )
    return float(val or 0)


# ── İşçi funksiyaları ─────────────────────────────────────────────────────────

async def add_worker(telegram_id: int, name: str, phone: str,
                     role: str, daily_rate: float) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO workers (telegram_id, name, phone, role, daily_rate)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
    """, telegram_id, name, phone, role, daily_rate)


async def get_workers() -> list:
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM workers ORDER BY name")
    return [dict(r) for r in rows]


async def get_worker(worker_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM workers WHERE id=$1", worker_id)
    return dict(row) if row else None


async def assign_worker(smeta_number: str, worker_id: int, start_date: str,
                        end_date: str = "", notes: str = "") -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO worker_assignments (smeta_number, worker_id, start_date, end_date, notes)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
    """, smeta_number, worker_id, start_date, end_date, notes)


async def get_worker_assignments(smeta_number: str = None, worker_id: int = None) -> list:
    pool = await get_pool()
    if smeta_number:
        rows = await pool.fetch("""
            SELECT wa.*, w.name, w.role, w.phone, w.daily_rate
            FROM worker_assignments wa
            JOIN workers w ON w.id = wa.worker_id
            WHERE wa.smeta_number=$1
        """, smeta_number)
        return [dict(r) for r in rows]
    elif worker_id:
        rows = await pool.fetch(
            "SELECT * FROM worker_assignments WHERE worker_id=$1 ORDER BY start_date DESC",
            worker_id
        )
        return [dict(r) for r in rows]
    return []


async def add_worker_payment(smeta_number: str, worker_id: int, amount: float,
                             date: str, notes: str = "", created_by: int = 0) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO worker_payments (smeta_number, worker_id, amount, date, notes, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """, smeta_number, worker_id, amount, date, notes, created_by)


async def get_worker_payments_by_month(worker_id: int, month: str) -> list:
    """month = '2026-03' format"""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT wp.*, w.name as worker_name, w.role
        FROM worker_payments wp
        JOIN workers w ON w.id = wp.worker_id
        WHERE wp.worker_id=$1 AND TO_CHAR(wp.created_at, 'YYYY-MM')=$2
        ORDER BY wp.created_at DESC
    """, worker_id, month)
    return [dict(r) for r in rows]


# ── Xatırlatma funksiyaları ───────────────────────────────────────────────────

async def add_reminder(smeta_number: str, message: str, remind_at: str,
                       created_by: int = 0) -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO reminders (smeta_number, message, remind_at, created_by)
        VALUES ($1, $2, $3, $4)
        RETURNING id
    """, smeta_number, message, remind_at, created_by)


async def get_pending_reminders() -> list:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT * FROM reminders
        WHERE is_sent=0 AND remind_at::TIMESTAMPTZ <= NOW()
        ORDER BY remind_at
    """)
    return [dict(r) for r in rows]


async def mark_reminder_sent(reminder_id: int):
    pool = await get_pool()
    await pool.execute("UPDATE reminders SET is_sent=1 WHERE id=$1", reminder_id)


# ── Alış siyahısı funksiyaları ────────────────────────────────────────────────

async def add_shopping_item(smeta_number: str, item_name: str, unit: str,
                            qty: float, priority: str = "normal",
                            notes: str = "") -> int:
    pool = await get_pool()
    return await pool.fetchval("""
        INSERT INTO shopping_list (smeta_number, item_name, unit, qty, priority, status, notes)
        VALUES ($1, $2, $3, $4, $5, 'pending', $6)
        RETURNING id
    """, smeta_number, item_name, unit, qty, priority, notes)


async def get_shopping_list(smeta_number: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM shopping_list WHERE smeta_number=$1 ORDER BY priority, created_at",
        smeta_number
    )
    return [dict(r) for r in rows]


async def update_shopping_item(item_id: int, status: str,
                               price_paid: float = 0, notes: str = ""):
    pool = await get_pool()
    await pool.execute("""
        UPDATE shopping_list SET status=$1, price_paid=$2, notes=$3
        WHERE id=$4
    """, status, price_paid, notes, item_id)


# ── Material foto ─────────────────────────────────────────────────────────────

async def save_material_photo(material_id: int, smeta_number: str, file_id: str,
                              caption: str = "", uploaded_by: int = 0):
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO material_photos (material_id, smeta_number, file_id, caption, uploaded_by)
        VALUES ($1, $2, $3, $4, $5)
    """, material_id, smeta_number, file_id, caption, uploaded_by)


async def get_material_photos(smeta_number: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM material_photos WHERE smeta_number=$1 ORDER BY created_at DESC",
        smeta_number
    )
    return [dict(r) for r in rows]


# ── Aylıq hesabat ─────────────────────────────────────────────────────────────

async def get_monthly_report(month: str) -> dict:
    """month = '2026-03' formatında"""
    pool = await get_pool()

    row = await pool.fetchrow("""
        SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total_value
        FROM smetas WHERE TO_CHAR(created_at, 'YYYY-MM')=$1
    """, month)
    new_smetas  = row["count"]
    total_value = float(row["total_value"] or 0)

    completed = await pool.fetchval("""
        SELECT COUNT(*) FROM smetas
        WHERE status='approved' AND TO_CHAR(updated_at, 'YYYY-MM')=$1
    """, month)

    active = await pool.fetchval(
        "SELECT COUNT(*) FROM smetas WHERE status='active'"
    )

    received_payments = float(await pool.fetchval("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payments WHERE TO_CHAR(created_at, 'YYYY-MM')=$1
    """, month) or 0)

    material_costs = float(await pool.fetchval("""
        SELECT COALESCE(SUM(price_paid), 0)
        FROM shopping_list WHERE status='bought' AND TO_CHAR(created_at, 'YYYY-MM')=$1
    """, month) or 0)

    worker_costs = float(await pool.fetchval("""
        SELECT COALESCE(SUM(amount), 0)
        FROM worker_payments WHERE TO_CHAR(created_at, 'YYYY-MM')=$1
    """, month) or 0)

    total_approved = float(await pool.fetchval(
        "SELECT COALESCE(SUM(total), 0) FROM smetas WHERE status='approved'"
    ) or 0)

    total_received_all = float(await pool.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM payments"
    ) or 0)

    expected_payments = max(0, total_approved - total_received_all)
    profit = received_payments - material_costs - worker_costs

    return {
        "month":             month,
        "new_smetas":        new_smetas,
        "completed":         completed,
        "active":            active,
        "total_value":       total_value,
        "received_payments": received_payments,
        "expected_payments": expected_payments,
        "material_costs":    material_costs,
        "worker_costs":      worker_costs,
        "profit":            profit,
    }


async def get_all_smetas_for_report(month: str) -> list:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT s.smeta_number, s.client_name, s.total, s.status, s.created_at,
               COALESCE((SELECT SUM(p.amount) FROM payments p
                         WHERE p.smeta_number=s.smeta_number), 0) as paid
        FROM smetas s
        WHERE TO_CHAR(s.created_at, 'YYYY-MM')=$1
        ORDER BY s.created_at
    """, month)
    return [dict(r) for r in rows]


async def get_all_smetas_admin() -> list:
    """Admin üçün bütün smetalar"""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, smeta_number, client_name, total, status, created_at, telegram_id "
        "FROM smetas ORDER BY created_at DESC LIMIT 50"
    )
    return [dict(r) for r in rows]
