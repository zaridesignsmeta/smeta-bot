"""
Konfiqurasiya - Bütün parametrləri buradan idarə edin
"""

import os

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "BU_YERE_BOT_TOKENINIZI_YAZIN")

# ── Admin istifadəçilər (Telegram User ID) ────────────────────────────────────
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")
    # Öz Telegram ID-nizi yazın: @userinfobot vasitəsilə tapa bilərsiniz
]

# ── Şirkət məlumatları ────────────────────────────────────────────────────────
COMPANY_NAME = "Zari Design"
COMPANY_PHONE = "+994 50 444 09 00"
COMPANY_EMAIL = "zaridesign.az"
COMPANY_ADDRESS = "3 Mərkəzi bulvar küçəsi, Bakı"
COMPANY_LOGO = "assets/logo.png"

# ── Maliyyə parametrləri ──────────────────────────────────────────────────────
CURRENCY = "AZN"
DEFAULT_VAT = 18          # ƏDV faizi (%)
DEFAULT_MARGIN = 20       # Marja / qazanc faizi (%)
DEFAULT_DISCOUNT = 0      # Standart endirim (%)

# ── Verilənlər bazası ─────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///smeta_bot.db")
# PostgreSQL üçün: postgresql+asyncpg://user:password@localhost/smeta_db

# ── Fayllar ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"   # Excel və PDF faylları buraya saxlanır

# ── Otaqlar siyahısı (tam mənzil şablonu üçün) ────────────────────────────────
ROOMS = [
    "Qonaq otağı",
    "Yataq otağı",
    "Uşaq otağı",
    "Mətbəx",
    "Hamam",
    "Tualet",
    "Koridor / Hol",
    "Balkon / Terras",
]

# ── Obyekt növləri ────────────────────────────────────────────────────────────
OBJECT_TYPES = {
    "🏠 Mənzil":           "manзil",
    "🏡 Villa":             "villa",
    "🏢 Ofis":              "ofis",
    "🏪 Ticarət obyekti":  "ticaret",
    "🏨 Otel / Hostel":    "otel",
    "🏗️ Digər":            "diger",
}

# Obyekt növünə görə otaqlar
OBJECT_ROOMS = {
    "manзil": [
        "Qonaq otağı", "Yataq otağı", "Uşaq otağı",
        "Mətbəx", "Hamam", "Tualet", "Koridor / Hol", "Balkon / Terras",
    ],
    "villa": [
        "Qonaq otağı", "Yataq otağı", "Uşaq otağı", "Master yataq otağı",
        "Mətbəx", "Hamam", "Tualet", "Koridor / Hol",
        "Zirzəmi", "Qaraj", "Hovuz otağı", "Terras / Veranda",
    ],
    "ofis": [
        "Açıq iş sahəsi", "Toplantı otağı", "Kabinet",
        "Resepsion", "Mətbəx / Qəhvəxana", "Hamam / Tualet",
        "Server otağı", "Anbar",
    ],
    "ticaret": [
        "Satış zalı", "Anbar", "Hamam / Tualet",
        "Ofis hissəsi", "Texniki otaq",
    ],
    "otel": [
        "Standart otaq", "Lüks otaq", "Süit otaq",
        "Resepsion / Lobbi", "Restoran / Bar", "Konfrans zalı",
        "Hamam / Tualet (ümumi)", "Texniki otaq",
    ],
    "diger": [
        "Otaq 1", "Otaq 2", "Otaq 3", "Hamam", "Mətbəx", "Digər sahə",
    ],
}

# ── Qiymət kateqoriyaları (işçilik üzrə) ─────────────────────────────────────
PRICE_CATEGORIES = {
    "🥈 Standart — 250 AZN/m²": {
        "key": "standart",
        "price_per_m2": 250,
        "multiplier": 1.0,
        "includes": [
            "Bütün malyar işləri (suvaq, şpatlevka, boya)",
            "Alçipan tavan + malyar işləri",
            "Bütün döşəmə işləri (laminat, kafel, stryajka)",
            "Bütün elektrik işləri",
            "Standart santexnika işləri",
            "Hamam (standart format, max 120x60 keramogranit)",
            "Ara kəsmələr",
            "Standart plintus",
            "Pəncərə kənarları (malyar)",
            "Qapı hazırlığı (quraşdırma daxil deyil)",
        ],
        "excludes": [
            "Stekloxolst",
            "Gizli profil / kölgə profil / pərdə boşluğu",
            "Gizli spotlar",
            "Böyük format keramogranit (100x300+)",
            "Gizli plintus",
            "Ağıllı ev sistemi",
            "Mühəndis həlləri / layihəsi",
            "Kondisioner quraşdırması",
            "Pilləkən işləri",
            "Balkon / Terras / Qaraj",
        ],
    },
    "🥇 Orta — 350 AZN/m²": {
        "key": "orta",
        "price_per_m2": 350,
        "multiplier": 1.4,
        "includes": [
            "Standart kateqoriyanın hər şeyi",
            "Stekloxolst",
            "Gizli profil / kölgə profil / pərdə boşluğu",
            "Gizli spotlar",
            "Böyük format keramogranit (100x300+)",
            "Gizli plintus",
        ],
        "excludes": [
            "Ağıllı ev sistemi",
            "Mühəndis həlləri / layihəsi",
            "Kondisioner quraşdırması",
            "Pilləkən işləri",
            "Balkon / Terras / Qaraj",
        ],
    },
    "💎 Premium — 500 AZN/m²": {
        "key": "premium",
        "price_per_m2": 500,
        "multiplier": 2.0,
        "includes": [
            "Orta kateqoriyanın hər şeyi",
            "Ağıllı ev sistemi",
            "Mühəndis həlləri / layihəsi",
        ],
        "excludes": [
            "Kondisioner quraşdırması",
            "Pilləkən işləri",
            "Balkon / Terras / Qaraj",
        ],
    },
}

# ── İş növləri ────────────────────────────────────────────────────────────────
WORK_CATEGORIES = {
    "🔨 Sökülüb-yığılma işləri": [
        ("Divar sökülməsi (m²)", 8),
        ("Köhnə döşəmə sökülməsi (m²)", 5),
        ("Köhnə kafel sökülməsi (m²)", 6),
        ("Kənar materialların aparılması (m³)", 15),
    ],
    "🏗️ Divar işləri": [
        ("Suvaq (m²)", 12),
        ("Şpatlevka (m²)", 8),
        ("Hamarlanma (m²)", 5),
        ("Boya (m²)", 6),
        ("Dekorativ suvaq (m²)", 18),
        ("Kafel döşənməsi (m²)", 20),
        ("Gips karton quruluşu (m²)", 25),
    ],
    "🏠 Tavan işləri": [
        ("Gərgin tavan (m²)", 35),
        ("Gips karton tavan (m²)", 28),
        ("Boya ilə boyama (m²)", 7),
        ("Hazır tavan (m²)", 22),
    ],
    "🪵 Döşəmə işləri": [
        ("Laminat döşənməsi (m²)", 10),
        ("Parket döşənməsi (m²)", 18),
        ("Kafel döşənməsi (m²)", 20),
        ("Epoksi döşəmə (m²)", 45),
        ("Hamarlanma / sement stryajka (m²)", 15),
    ],
    "🚰 Santexnika işləri": [
        ("Santexnika quraşdırılması (ədəd)", 80),
        ("Boru xətti (m)", 25),
        ("Hamam quraşdırılması (ədəd)", 150),
        ("Duş kabinası (ədəd)", 120),
        ("Unitaz (ədəd)", 60),
        ("Lavabo (ədəd)", 50),
    ],
    "⚡ Elektrik işləri": [
        ("Elektrik xətti (m)", 8),
        ("Rozetka/Açar quraşdırılması (ədəd)", 15),
        ("Qoşulma qutusu (ədəd)", 25),
        ("İşıqlandırma (nöqtə)", 20),
        ("Elektrik paneli (ədəd)", 200),
    ],
    "🚪 Qapı / Pəncərə işləri": [
        ("İç qapı quraşdırılması (ədəd)", 80),
        ("Giriş qapısı (ədəd)", 120),
        ("Plastik pəncərə quraşdırılması (ədəd)", 100),
        ("Penoplast / İzolyasiya (m²)", 15),
    ],
    "🧱 Divar / Ara Kəsmələr (iş)": [
        ("Kərpic hörməsi (m²)", 8),
        ("Beton blok hörməsi (m²)", 10),
        ("Gips blok hörməsi (m²)", 9),
        ("Alçipan ara kəsmə - 2 tərəfli (m²)", 14),
        ("Daş hörməsi (m²)", 12),
        ("Ara kəsmə sökülməsi (m²)", 6),
    ],
    "📦 Materiallar": [
        ("Kərpic (ədəd)", 0.35),
        ("Beton blok (ədəd)", 2.5),
        ("Gips blok (m²)", 8),
        ("Alçipan lövhə - 2 tərəf (m²)", 14),
        ("Kubik daş (m³)", 45),
        ("Sement (kisə)", 12),
        ("Qum (m³)", 25),
        ("Əhəng (kisə)", 8),
        ("Karkas profil (m)", 3.5),
        ("Mineral pambıq izolyasiya (m²)", 6),
    ],
}
