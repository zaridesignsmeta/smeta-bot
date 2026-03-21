from flask import Flask, render_template_string
import aiosqlite
import asyncio
import json
import os

app = Flask(__name__)

TEMPLATE = """
<!DOCTYPE html>
<html lang="az">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smeta {{ smeta.smeta_number }} - Zari Design</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: Arial, sans-serif; background:#f5f6fa; color:#333; }
.header { background:#1B2A4A; color:white; padding:20px 30px; display:flex; align-items:center; gap:20px; }
.header h1 { font-size:24px; }
.header p { color:#C9973A; font-size:14px; }
.header .contact { margin-left:auto; text-align:right; font-size:13px; color:#aaa; }
.container { max-width:900px; margin:30px auto; padding:0 20px; }
.info-box { background:white; border-radius:8px; padding:20px; margin-bottom:20px; display:grid; grid-template-columns:1fr 1fr; gap:10px; box-shadow:0 2px 8px rgba(0,0,0,0.07); }
.info-box .label { color:#888; font-size:13px; }
.info-box .value { font-weight:bold; }
.room { margin-bottom:20px; }
.room-title { background:#C9973A; color:white; padding:10px 15px; border-radius:6px 6px 0 0; font-weight:bold; }
table { width:100%; border-collapse:collapse; background:white; box-shadow:0 2px 8px rgba(0,0,0,0.07); }
th { background:#1B2A4A; color:white; padding:10px; text-align:left; font-size:13px; }
td { padding:9px 10px; font-size:13px; border-bottom:1px solid #eee; }
tr:nth-child(even) { background:#f9fafb; }
.cat-row td { background:#DDE1EA; font-style:italic; font-weight:bold; color:#1B2A4A; }
.totals { background:white; border-radius:8px; padding:20px; margin-top:20px; box-shadow:0 2px 8px rgba(0,0,0,0.07); }
.total-row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #eee; font-size:14px; }
.grand-total { display:flex; justify-content:space-between; padding:15px; background:#1B2A4A; color:white; border-radius:6px; margin-top:10px; font-size:18px; font-weight:bold; }
.badge { display:inline-block; padding:4px 10px; border-radius:20px; font-size:12px; }
.draft { background:#fff3cd; color:#856404; }
.approved { background:#d4edda; color:#155724; }
.sent { background:#cce5ff; color:#004085; }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>ZARI DESIGN</h1>
    <p>TƏMİR SMETASİ</p>
  </div>
  <div class="contact">
    +994 50 444 09 00<br>
    3 Mərkəzi bulvar küçəsi, Bakı
  </div>
</div>
<div class="container">
  <div class="info-box">
    <div><div class="label">Smeta №</div><div class="value">{{ smeta.smeta_number }}</div></div>
    <div><div class="label">Tarix</div><div class="value">{{ smeta.created_at[:10] }}</div></div>
    <div><div class="label">Müştəri</div><div class="value">{{ smeta.client_name }}</div></div>
    <div><div class="label">Telefon</div><div class="value">{{ smeta.client_phone }}</div></div>
    <div><div class="label">Ünvan</div><div class="value">{{ smeta.address }}</div></div>
    <div><div class="label">Status</div><div class="value">
      <span class="badge {{ smeta.status }}">{{ {'draft':'Qaralama','sent':'Göndərilib','approved':'Təsdiqlənib','rejected':'Rədd edilib'}.get(smeta.status, smeta.status) }}</span>
    </div></div>
  </div>

  {% for room, categories in rooms.items() %}
  <div class="room">
    <div class="room-title">📍 {{ room }}</div>
    <table>
      <tr><th>№</th><th>İşin adı</th><th>Ölçü</th><th>Miqdar</th><th>Qiymət (AZN)</th><th>Məbləğ (AZN)</th></tr>
      {% set ns = namespace(counter=1) %}
      {% for cat, items in categories.items() %}
      {% if items %}
      <tr class="cat-row"><td colspan="6">{{ cat }}</td></tr>
      {% for item in items %}
      <tr>
        <td>{{ ns.counter }}</td>
        <td>{{ item.name }}</td>
        <td>{{ item.unit }}</td>
        <td>{{ item.qty }}</td>
        <td>{{ "%.2f"|format(item.price) }}</td>
        <td>{{ "%.2f"|format(item.qty * item.price) }}</td>
      </tr>
      {% set ns.counter = ns.counter + 1 %}
      {% endfor %}
      {% endif %}
      {% endfor %}
    </table>
  </div>
  {% endfor %}

  <div class="totals">
    <div class="total-row"><span>Cəmi (işlər):</span><span>{{ "%.2f"|format(smeta.subtotal) }} AZN</span></div>
    <div class="total-row"><span>Marja ({{ smeta.margin_pct }}%):</span><span>{{ "%.2f"|format(smeta.subtotal * smeta.margin_pct / 100) }} AZN</span></div>
    {% if smeta.discount_pct > 0 %}
    <div class="total-row"><span>Endirim ({{ smeta.discount_pct }}%):</span><span>-{{ "%.2f"|format((smeta.subtotal + smeta.subtotal * smeta.margin_pct / 100) * smeta.discount_pct / 100) }} AZN</span></div>
    {% endif %}
    <div class="total-row"><span>ƏDV ({{ smeta.vat_pct }}%):</span><span>{{ "%.2f"|format(smeta.total * smeta.vat_pct / (100 + smeta.vat_pct)) }} AZN</span></div>
    <div class="grand-total"><span>YEKUNİ:</span><span>{{ "%.2f"|format(smeta.total) }} AZN</span></div>
  </div>
</div>
</body>
</html>
"""

async def get_smeta_async(smeta_number):
    db_path = os.getenv("DB_PATH", "smeta_bot.db")
    async with aiosqlite.connect(db_path) as db:
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

@app.route("/smeta/<smeta_number>")
def view_smeta(smeta_number):
    smeta = asyncio.run(get_smeta_async(smeta_number))
    if not smeta:
        return "<h2>Smeta tapılmadı</h2>", 404
    return render_template_string(TEMPLATE, smeta=smeta, rooms=smeta["rooms_data"])

@app.route("/")
def index():
    return "<h2>Zari Design Smeta Sistemi</h2>", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
