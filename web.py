from flask import Flask, render_template_string, abort
import aiosqlite
import asyncio
import json
import os

app = Flask(__name__)

TEMPLATE = """<!DOCTYPE html>
<html lang="az">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smeta {{ smeta.smeta_number }} — Zari Design</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background:#F0F2F5; color:#1a1a2e; }
  .header { background:#1B2A4A; padding:0; position:sticky; top:0; z-index:100; box-shadow:0 2px 20px rgba(0,0,0,0.3); }
  .header-inner { max-width:960px; margin:0 auto; padding:18px 24px; display:flex; align-items:center; justify-content:space-between; }
  .logo-text h1 { color:#fff; font-size:20px; font-weight:700; letter-spacing:2px; }
  .logo-text p { color:#C9973A; font-size:11px; letter-spacing:3px; text-transform:uppercase; margin-top:2px; }
  .header-contact { text-align:right; }
  .header-contact p { color:rgba(255,255,255,0.7); font-size:12px; line-height:1.8; }
  .header-contact strong { color:#fff; font-size:14px; }
  .page { max-width:960px; margin:32px auto; padding:0 16px 60px; }

  .smeta-hero { background:#fff; border-radius:16px; padding:28px 32px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,0.08); display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; }
  .hero-field label { font-size:11px; color:#888; text-transform:uppercase; letter-spacing:1px; display:block; margin-bottom:4px; }
  .hero-field p { font-size:15px; color:#1a1a2e; font-weight:500; }
  .status-badge { display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:20px; font-size:12px; font-weight:600; }
  .status-dot { width:7px; height:7px; border-radius:50%; }
  .status-draft { background:#FFF3CD; color:#856404; } .status-draft .status-dot { background:#FFC107; }
  .status-sent { background:#CCE5FF; color:#004085; } .status-sent .status-dot { background:#0D6EFD; }
  .status-approved { background:#D4EDDA; color:#155724; } .status-approved .status-dot { background:#28A745; }
  .status-rejected { background:#F8D7DA; color:#721C24; } .status-rejected .status-dot { background:#DC3545; }

  .section-title { font-size:13px; color:#888; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; font-weight:600; }

  .room-section { margin-bottom:20px; }
  .room-header { background:#1B2A4A; color:#fff; padding:14px 24px; border-radius:12px 12px 0 0; font-size:15px; font-weight:600; display:flex; align-items:center; justify-content:space-between; }
  .room-header::before { content:''; display:inline-block; width:4px; height:18px; background:#C9973A; border-radius:2px; margin-right:10px; }
  .room-total { color:#C9973A; font-size:14px; }

  .progress-bar-wrap { background:#243656; padding:12px 24px; }
  .progress-label { display:flex; justify-content:space-between; color:rgba(255,255,255,0.7); font-size:12px; margin-bottom:6px; }
  .progress-track { background:rgba(255,255,255,0.15); border-radius:10px; height:8px; overflow:hidden; }
  .progress-fill { height:100%; border-radius:10px; background:linear-gradient(90deg, #C9973A, #E8B96A); transition:width 0.5s; }

  .work-table { width:100%; border-collapse:collapse; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
  .work-table th { background:#F8F9FA; color:#6c757d; font-size:11px; text-transform:uppercase; letter-spacing:0.8px; padding:10px 16px; text-align:left; font-weight:600; border-bottom:1px solid #E9ECEF; }
  .work-table th:last-child, .work-table td:last-child { text-align:right; }
  .work-table th:nth-child(3), .work-table th:nth-child(4), .work-table td:nth-child(3), .work-table td:nth-child(4) { text-align:center; }
  .work-table td { padding:10px 16px; font-size:13px; border-bottom:1px solid #F0F2F5; color:#333; }
  .work-table tr:last-child td { border-bottom:none; }
  .work-table tr:hover td { background:#FAFBFC; }
  .cat-row td { background:#F8F9FA !important; color:#1B2A4A; font-weight:600; font-size:12px; padding:8px 16px; border-bottom:1px solid #E9ECEF !important; }
  .amount-col { font-weight:600; color:#1B2A4A; }
  .room-subtotal-row td { background:#EEF0F5 !important; font-weight:700; color:#1B2A4A; border-top:2px solid #DDE1EA !important; }

  .photos-section { background:#fff; border-radius:0 0 12px 12px; padding:16px; border-top:1px solid #F0F2F5; }
  .photos-title { font-size:12px; color:#888; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:12px; }
  .photos-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(120px, 1fr)); gap:8px; }
  .photo-item { border-radius:8px; overflow:hidden; aspect-ratio:1; background:#F0F2F5; cursor:pointer; }
  .photo-item img { width:100%; height:100%; object-fit:cover; transition:transform 0.2s; }
  .photo-item:hover img { transform:scale(1.05); }
  .photo-caption { font-size:11px; color:#888; margin-top:4px; text-align:center; }

  .lightbox { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; align-items:center; justify-content:center; }
  .lightbox.active { display:flex; }
  .lightbox img { max-width:90%; max-height:90%; border-radius:8px; }
  .lightbox-close { position:absolute; top:20px; right:20px; color:#fff; font-size:30px; cursor:pointer; }

  .totals-card { background:#fff; border-radius:16px; padding:28px 32px; margin-top:24px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
  .total-line { display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #F0F2F5; font-size:14px; }
  .total-line:last-of-type { border-bottom:none; }
  .total-line span:first-child { color:#666; }
  .total-line span:last-child { font-weight:600; color:#1a1a2e; }
  .grand-total-box { background:#1B2A4A; border-radius:12px; padding:20px 24px; margin-top:20px; display:flex; justify-content:space-between; align-items:center; }
  .grand-total-box .label { color:rgba(255,255,255,0.7); font-size:13px; text-transform:uppercase; letter-spacing:1px; }
  .grand-total-box .amount { color:#fff; font-size:28px; font-weight:700; }
  .grand-total-box .currency { color:#C9973A; font-size:16px; margin-left:6px; }
  .notes-box { background:#FFFBF0; border-left:3px solid #C9973A; border-radius:0 8px 8px 0; padding:14px 18px; margin-top:20px; font-size:13px; color:#666; }
  .footer { text-align:center; margin-top:48px; color:#aaa; font-size:12px; }
  .footer strong { color:#C9973A; }
  @media (max-width:640px) {
    .smeta-hero { grid-template-columns:1fr 1fr; }
    .header-contact { display:none; }
    .grand-total-box .amount { font-size:22px; }
  }
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="logo-text">
      <h1>ZARI DESIGN</h1>
      <p>Təmir Smetası</p>
    </div>
    <div class="header-contact">
      <strong>+994 50 444 09 00</strong>
      <p>3 Mərkəzi bulvar küçəsi, Bakı</p>
    </div>
  </div>
</div>

<div class="page">

  <div class="smeta-hero">
    <div class="hero-field"><label>Smeta nömrəsi</label><p>{{ smeta.smeta_number }}</p></div>
    <div class="hero-field"><label>Tarix</label><p>{{ smeta.created_at[:10] }}</p></div>
    <div class="hero-field"><label>Status</label>
      <span class="status-badge status-{{ smeta.status }}">
        <span class="status-dot"></span>
        {{ {'draft':'Qaralama','sent':'Göndərilib','approved':'Təsdiqlənib','rejected':'Rədd edilib'}.get(smeta.status, smeta.status) }}
      </span>
    </div>
    <div class="hero-field"><label>Müştəri</label><p>{{ smeta.client_name }}</p></div>
    <div class="hero-field"><label>Telefon</label><p>{{ smeta.client_phone }}</p></div>
    <div class="hero-field"><label>Ünvan</label><p>{{ smeta.address }}</p></div>
  </div>

  {% set ns = namespace(counter=1) %}
  {% for room, categories in rooms.items() %}
  {% set room_total = namespace(val=0) %}
  {% for cat, items in categories.items() %}
  {% for item in items %}{% set room_total.val = room_total.val + item.qty * item.price %}{% endfor %}
  {% endfor %}
  {% set progress = progress_data.get(room, {}).get('progress_pct', 0) %}
  {% set room_photos = photos_by_room.get(room, []) %}

  <div class="room-section">
    <div class="room-header">
      <span>{{ room }}</span>
      <span class="room-total">{{ "%.2f"|format(room_total.val) }} AZN</span>
    </div>

    <div class="progress-bar-wrap">
      <div class="progress-label">
        <span>İş gedişatı</span>
        <span>{{ progress }}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:{{ progress }}%"></div>
      </div>
    </div>

    <table class="work-table">
      <thead><tr>
        <th style="width:44px">№</th>
        <th>İşin adı</th>
        <th style="width:80px">Ölçü</th>
        <th style="width:80px">Miqdar</th>
        <th style="width:110px">Qiymət (AZN)</th>
        <th style="width:120px">Məbləğ (AZN)</th>
      </tr></thead>
      <tbody>
        {% for cat, items in categories.items() %}
        {% if items %}
        <tr class="cat-row"><td colspan="6">{{ cat }}</td></tr>
        {% for item in items %}
        <tr>
          <td style="color:#aaa">{{ ns.counter }}</td>
          <td>{{ item.name }}</td>
          <td style="text-align:center">{{ item.unit }}</td>
          <td style="text-align:center">{{ item.qty }}</td>
          <td style="text-align:right">{{ "%.2f"|format(item.price) }}</td>
          <td class="amount-col">{{ "%.2f"|format(item.qty * item.price) }}</td>
        </tr>
        {% set ns.counter = ns.counter + 1 %}
        {% endfor %}
        {% endif %}
        {% endfor %}
        <tr class="room-subtotal-row">
          <td colspan="5" style="text-align:right; padding-right:16px;">{{ room }} cəmi:</td>
          <td>{{ "%.2f"|format(room_total.val) }} AZN</td>
        </tr>
      </tbody>
    </table>

    {% if room_photos %}
    <div class="photos-section">
      <div class="photos-title">📸 Fotolar ({{ room_photos|length }})</div>
      <div class="photos-grid">
        {% for photo in room_photos %}
        <div class="photo-item" onclick="openLightbox('{{ photo.file_id }}')">
          <img src="/photo/{{ photo.file_id }}" alt="{{ photo.caption }}" loading="lazy">
        </div>
        {% if photo.caption %}
        <div class="photo-caption">{{ photo.caption }}</div>
        {% endif %}
        {% endfor %}
      </div>
    </div>
    {% endif %}

  </div>
  {% endfor %}

  <div class="totals-card">
    <h3 class="section-title">Hesablama</h3>
    <div class="total-line"><span>İşçilik və işlər</span><span>{{ "%.2f"|format(smeta.total) }} AZN</span></div>
    {% if smeta.discount_pct > 0 %}
    {% set discount = smeta.total * smeta.discount_pct / 100 %}
    <div class="total-line" style="color:#28a745"><span>Endirim ({{ smeta.discount_pct }}%)</span><span>−{{ "%.2f"|format(discount) }} AZN</span></div>
    {% endif %}
    <div class="grand-total-box">
      <div class="label">Yekun məbləğ</div>
      <div><span class="amount">{{ "%.2f"|format(smeta.total) }}</span><span class="currency">AZN</span></div>
    </div>
    {% if smeta.notes %}
    <div class="notes-box">📝 {{ smeta.notes }}</div>
    {% endif %}
  </div>

  <div class="footer">
    <p>Bu smeta <strong>Zari Design</strong> tərəfindən hazırlanmışdır</p>
    <p style="margin-top:4px">+994 50 444 09 00 · 3 Mərkəzi bulvar küçəsi, Bakı</p>
  </div>

</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">×</span>
  <img id="lightbox-img" src="" alt="">
</div>

<script>
function openLightbox(fileId) {
  document.getElementById('lightbox-img').src = '/photo/' + fileId;
  document.getElementById('lightbox').classList.add('active');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('active');
}
</script>
</body>
</html>"""


async def get_data_async(smeta_number):
    db_path = os.getenv("DB_PATH", "smeta_bot.db")
    result = {}
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Smeta
        async with db.execute("SELECT * FROM smetas WHERE smeta_number=?", (smeta_number,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["rooms_data"] = json.loads(d["rooms_data"])
            result["smeta"] = d

        # Progress
        progress = {}
        try:
            async with db.execute("SELECT * FROM room_progress WHERE smeta_number=?", (smeta_number,)) as cur:
                for row in await cur.fetchall():
                    r = dict(row)
                    progress[r["room_name"]] = r
        except Exception:
            pass
        result["progress"] = progress

        # Photos
        photos = []
        try:
            async with db.execute(
                "SELECT * FROM smeta_photos WHERE smeta_number=? ORDER BY created_at DESC",
                (smeta_number,)
            ) as cur:
                photos = [dict(r) for r in await cur.fetchall()]
        except Exception:
            pass

        photos_by_room = {}
        for p in photos:
            room = p.get("room_name", "Ümumi")
            if room not in photos_by_room:
                photos_by_room[room] = []
            photos_by_room[room].append(p)
        result["photos_by_room"] = photos_by_room

    return result


@app.route("/smeta/<smeta_number>")
def view_smeta(smeta_number):
    data = asyncio.run(get_data_async(smeta_number))
    if not data:
        return "<div style='font-family:Arial;text-align:center;padding:80px;color:#888'><h2>Smeta tapılmadı</h2></div>", 404
    return render_template_string(
        TEMPLATE,
        smeta=data["smeta"],
        rooms=data["smeta"]["rooms_data"],
        progress_data=data["progress"],
        photos_by_room=data["photos_by_room"]
    )


@app.route("/photo/<file_id>")
def get_photo(file_id):
    """Telegram foto linki — bot vasitəsilə yüklənir"""
    import requests
    bot_token = os.getenv("BOT_TOKEN", "")
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}", timeout=5)
        file_path = r.json()["result"]["file_path"]
        photo = requests.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}", timeout=10)
        from flask import Response
        return Response(photo.content, mimetype="image/jpeg")
    except Exception:
        return "", 404


@app.route("/")
def index():
    return "<div style='font-family:Arial;text-align:center;padding:80px'><h1 style='color:#1B2A4A'>Zari Design</h1><p style='color:#C9973A'>Təmir Smeta Sistemi</p></div>", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
