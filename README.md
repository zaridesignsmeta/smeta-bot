# 🤖 Smeta Bot — Quraşdırma Təlimatı

## 📁 Fayl Strukturu
```
smeta_bot/
├── bot.py           ← Əsas başlatma faylı
├── config.py        ← Bütün tənzimləmələr
├── database.py      ← Verilənlər bazası
├── handlers.py      ← Telegram komandaları
├── generators.py    ← Excel + PDF yaradan
├── requirements.txt ← Paketlər
├── .env.example     ← Nümunə konfiqurasiya
└── output/          ← Yaranan fayllar (avtomatik)
```

---

## ⚙️ ADDIM 1: Bot Token Alın

1. Telegram-da `@BotFather`-a yazın
2. `/newbot` göndərin
3. Ad verin: `Farid Smeta Bot`
4. Username verin: `farid_smeta_bot`
5. **Token**u kopyalayın (bu formatda: `7123456789:AAF...`)

---

## 💻 ADDIM 2: Kompüterdə Quraşdırmaq

### Windows:
```bash
# Python 3.11+ yükləyin: python.org
# Sonra CMD-də:
cd smeta_bot
pip install -r requirements.txt
copy .env.example .env
# .env faylını notepad ilə açıb BOT_TOKEN-i yazın
python bot.py
```

### Linux/Mac:
```bash
cd smeta_bot
pip install -r requirements.txt
cp .env.example .env
nano .env   # BOT_TOKEN yazın
python bot.py
```

---

## ☁️ ADDIM 3: Server-də İşlətmək (24/7)

### Railway.app (Pulsuz, ən asan):
1. https://railway.app qeydiyyat
2. "New Project" → "Deploy from GitHub"
3. Repozu yükləyin
4. Environment Variables:
   - `BOT_TOKEN` = tokeniniz
   - `ADMIN_IDS` = telegram id-niz
5. Deploy!

### VPS (DigitalOcean/Hetzner):
```bash
# Ubuntu server:
sudo apt install python3 python3-pip screen -y
pip3 install -r requirements.txt
screen -S smeta_bot
python3 bot.py
# Ctrl+A, D (arxa plana keçir)
```

---

## 📱 ADDIM 4: Telegram ID-nizi tapın

1. `@userinfobot`-a yazın
2. `/start` göndərin
3. `Id:` sahəsindəki rəqəmi `.env`-ə yazın

---

## 🤖 Bot Komandaları

| Komanda | Funksiya |
|---------|----------|
| `/start` | Ana menyu |
| 📋 Yeni Smeta | Yeni smeta yaratmaq |
| 📁 Smetalarım | Keçmiş smetalar |
| 🏗️ Layihələr | Aktiv layihələr |
| 📊 Statistika | Gəlir statistikası |
| `/newproject` | Yeni layihə əlavə et |

---

## 🔧 Config.py-da Dəyişdirə Biləcəkləriniz

```python
COMPANY_NAME = "Farid Təmir & Dizayn"  # Şirkət adı
COMPANY_PHONE = "+994 XX XXX XX XX"     # Telefon
DEFAULT_VAT = 18                         # ƏDV %
DEFAULT_MARGIN = 20                      # Marja %
```

---

## ❓ Problemlər

**Bot cavab vermir:**
- Token düzgün yazılıb?
- `python bot.py` işləyirmi?

**Excel açılmır:**
- `pip install openpyxl` yenidən çalışdırın

**PDF boş çıxır:**
- `pip install reportlab` yenidən çalışdırın

---

## 🚀 Növbəti Mərhələlər

1. ✅ Smeta Botu (hazır)
2. 🔜 Layihə İzləmə (foto göndərmə, %-li gedişat)
3. 🔜 Mühasibat Botu (gəlir/xərc izləmə)
4. 🔜 Müştəri Botu (qiymət sorğusu, status yoxlama)
5. 🔜 Admin Panel (veb interfeys)
