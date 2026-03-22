from flask import Flask, render_template_string, Response
import asyncpg
import asyncio
import json
import os
import requests as req_lib
from datetime import datetime

app = Flask(__name__)

PAYMENT_TYPE_LABELS = {
    "advance": "💰 Avans",
    "interim": "💵 Ara ödəniş",
    "final":   "✅ Son ödəniş",
}

TEMPLATE = """<!DOCTYPE html>
<html lang="az">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Smeta {{ smeta.smeta_number }} — Zari Design</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',Arial,sans-serif; background:#F0F2F5; color:#1a1a2e; }

.header { background:#1B2A4A; padding:0; position:sticky; top:0; z-index:100; box-shadow:0 2px 20px rgba(0,0,0,0.3); }
.header-inner { max-width:960px; margin:0 auto; padding:16px 24px; display:flex; align-items:center; justify-content:space-between; }
.logo-text h1 { color:#fff; font-size:18px; font-weight:700; letter-spacing:2px; }
.logo-text p { color:#C9973A; font-size:10px; letter-spacing:3px; text-transform:uppercase; margin-top:2px; }
.header-contact { text-align:right; }
.header-contact p { color:rgba(255,255,255,0.6); font-size:11px; line-height:1.8; }
.header-contact strong { color:#fff; font-size:13px; }

.page { max-width:960px; margin:0 auto; padding:24px 16px 60px; }

.smeta-hero { background:#fff; border-radius:12px; padding:24px 28px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.08); display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
.hero-field label { font-size:10px; color:#888; text-transform:uppercase; letter-spacing:1px; display:block; margin-bottom:3px; }
.hero-field p { font-size:14px; color:#1a1a2e; font-weight:500; }
.status-badge { display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border-radius:20px; font-size:11px; font-weight:600; }
.status-dot { width:6px; height:6px; border-radius:50%; }
.status-draft { background:#FFF3CD; color:#856404; } .status-draft .status-dot { background:#FFC107; }
.status-sent { background:#CCE5FF; color:#004085; } .status-sent .status-dot { background:#0D6EFD; }
.status-approved { background:#D4EDDA; color:#155724; } .status-approved .status-dot { background:#28A745; }
.status-rejected { background:#F8D7DA; color:#721C24; } .status-rejected .status-dot { background:#DC3545; }

.tabs { display:flex; background:#fff; border-radius:12px; padding:6px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.08); gap:4px; }
.tab { flex:1; padding:10px 8px; text-align:center; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer; color:#888; transition:all 0.2s; border:none; background:none; }
.tab.active { background:#1B2A4A; color:#fff; }
.tab-content { display:none; }
.tab-content.active { display:block; }

.room-section { margin-bottom:16px; }
.room-header { background:#1B2A4A; color:#fff; padding:12px 20px; border-radius:10px 10px 0 0; font-size:14px; font-weight:600; display:flex; align-items:center; justify-content:space-between; }
.room-header::before { content:''; display:inline-block; width:3px; height:16px; background:#C9973A; border-radius:2px; margin-right:10px; }
.room-total { color:#C9973A; font-size:13px; }

.progress-wrap { background:#243656; padding:10px 20px; }
.progress-label { display:flex; justify-content:space-between; color:rgba(255,255,255,0.6); font-size:11px; margin-bottom:5px; }
.progress-track { background:rgba(255,255,255,0.1); border-radius:10px; height:6px; }
.progress-fill { height:100%; border-radius:10px; background:linear-gradient(90deg,#C9973A,#E8B96A); }
.progress-note { color:rgba(255,255,255,0.5); font-size:11px; margin-top:5px; font-style:italic; }

.work-table { width:100%; border-collapse:collapse; background:#fff; }
.work-table th { background:#F8F9FA; color:#6c757d; font-size:10px; text-transform:uppercase; letter-spacing:0.8px; padding:9px 14px; text-align:left; font-weight:600; border-bottom:1px solid #E9ECEF; }
.work-table th:last-child, .work-table td:last-child { text-align:right; }
.work-table td { padding:9px 14px; font-size:12px; border-bottom:1px solid #F0F2F5; color:#333; }
.work-table tr:last-child td { border-bottom:none; }
.work-table tr:hover td { background:#FAFBFC; }
.cat-row td { background:#F8F9FA !important; color:#1B2A4A; font-weight:600; font-size:11px; padding:7px 14px; }
.zero-row td { color:#ccc; }
.amount-col { font-weight:600; color:#1B2A4A; }
.room-sub td { background:#EEF0F5 !important; font-weight:700; border-top:2px solid #DDE1EA !important; }

.photos-wrap { background:#fff; padding:14px; border-radius:0 0 10px 10px; border-top:1px solid #F0F2F5; }
.photos-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(100px,1fr)); gap:6px; margin-top:8px; }
.photo-item { border-radius:6px; overflow:hidden; aspect-ratio:1; cursor:pointer; }
.photo-item img { width:100%; height:100%; object-fit:cover; }

.totals-card { background:#fff; border-radius:12px; padding:24px 28px; margin-top:16px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.total-line { display:flex; justify-content:space-between; padding:9px 0; border-bottom:1px solid #F0F2F5; font-size:13px; }
.total-line:last-of-type { border-bottom:none; }
.total-line span:first-child { color:#666; }
.total-line span:last-child { font-weight:600; }
.grand-box { background:#1B2A4A; border-radius:10px; padding:18px 22px; margin-top:16px; display:flex; justify-content:space-between; align-items:center; }
.grand-box .lbl { color:rgba(255,255,255,0.6); font-size:12px; text-transform:uppercase; letter-spacing:1px; }
.grand-box .amt { color:#fff; font-size:26px; font-weight:700; }
.grand-box .cur { color:#C9973A; font-size:14px; margin-left:5px; }

.progress-cards { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.prog-card { background:#fff; border-radius:10px; padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.prog-card h4 { font-size:13px; color:#1B2A4A; margin-bottom:10px; font-weight:600; }
.prog-card-bar { background:#F0F2F5; border-radius:6px; height:8px; margin-bottom:6px; }
.prog-card-fill { height:100%; border-radius:6px; background:linear-gradient(90deg,#1B2A4A,#C9973A); }
.prog-pct { font-size:20px; font-weight:700; color:#1B2A4A; }
.prog-note { font-size:11px; color:#888; margin-top:4px; }
.next-step { background:#FFFBF0; border-left:3px solid #C9973A; padding:8px 12px; border-radius:0 6px 6px 0; font-size:12px; color:#666; margin-top:8px; }

.mat-list { background:#fff; border-radius:10px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.mat-item { display:flex; align-items:center; padding:12px 16px; border-bottom:1px solid #F0F2F5; gap:12px; }
.mat-item:last-child { border-bottom:none; }
.mat-icon { width:32px; height:32px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:16px; flex-shrink:0; }
.mat-bought { background:#D4EDDA; }
.mat-pending { background:#FFF3CD; }
.mat-missing { background:#F8D7DA; }
.mat-info { flex:1; }
.mat-name { font-size:13px; font-weight:600; color:#1a1a2e; }
.mat-detail { font-size:11px; color:#888; margin-top:2px; }
.mat-status { font-size:11px; font-weight:600; padding:3px 8px; border-radius:10px; }
.st-bought { background:#D4EDDA; color:#155724; }
.st-pending { background:#FFF3CD; color:#856404; }
.st-missing { background:#F8D7DA; color:#721C24; }
.mat-empty { text-align:center; padding:40px; color:#aaa; font-size:13px; }

.check-room { margin-bottom:16px; }
.check-room-title { font-size:13px; font-weight:700; color:#1B2A4A; padding:10px 16px; background:#fff; border-radius:8px 8px 0 0; border-bottom:1px solid #F0F2F5; }
.check-items { background:#fff; border-radius:0 0 8px 8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.check-item { display:flex; align-items:center; padding:10px 16px; border-bottom:1px solid #F0F2F5; gap:10px; }
.check-item:last-child { border-bottom:none; }
.check-box { width:20px; height:20px; border-radius:5px; display:flex; align-items:center; justify-content:center; flex-shrink:0; font-size:12px; }
.checked { background:#D4EDDA; color:#155724; }
.unchecked { background:#F0F2F5; color:#aaa; }
.check-text { font-size:13px; flex:1; }
.check-text.done { color:#888; text-decoration:line-through; }
.check-meta { font-size:10px; color:#aaa; }

.notes-box { background:#FFFBF0; border-left:3px solid #C9973A; border-radius:0 6px 6px 0; padding:12px 16px; margin-top:16px; font-size:12px; color:#666; }
.footer { text-align:center; margin-top:40px; color:#aaa; font-size:11px; }
.footer strong { color:#C9973A; }

/* Payment tab */
.pay-summary { background:#fff; border-radius:10px; padding:18px 22px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.pay-bar-wrap { background:#F0F2F5; border-radius:8px; height:10px; margin:10px 0 6px; }
.pay-bar-fill { height:100%; border-radius:8px; background:linear-gradient(90deg,#1B2A4A,#C9973A); }
.pay-list { background:#fff; border-radius:10px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.pay-item { display:flex; align-items:flex-start; padding:14px 16px; border-bottom:1px solid #F0F2F5; gap:12px; }
.pay-item:last-child { border-bottom:none; }
.pay-icon { width:36px; height:36px; border-radius:9px; display:flex; align-items:center; justify-content:center; font-size:17px; flex-shrink:0; background:#EEF2FF; }
.pay-info { flex:1; }
.pay-amount { font-size:16px; font-weight:700; color:#1B2A4A; }
.pay-type { font-size:11px; color:#888; margin-top:2px; }
.pay-cats { display:flex; gap:6px; margin-top:6px; flex-wrap:wrap; }
.pay-cat { font-size:10px; padding:2px 8px; border-radius:10px; background:#F0F2F5; color:#555; }
.pay-date { font-size:11px; color:#aaa; white-space:nowrap; }

.lightbox { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.92); z-index:1000; align-items:center; justify-content:center; }
.lightbox.open { display:flex; }
.lightbox img { max-width:92%; max-height:88%; border-radius:8px; }
.lb-close { position:absolute; top:18px; right:18px; color:#fff; font-size:28px; cursor:pointer; }

@media(max-width:640px){
.smeta-hero { grid-template-columns:1fr 1fr; }
.header-contact { display:none; }
.progress-cards { grid-template-columns:1fr; }
.tab { font-size:10px; padding:8px 4px; }
}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="logo-text"><h1>ZARI DESIGN</h1><p>Təmir Smetası</p></div>
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

  <div class="tabs">
    <button class="tab active" onclick="showTab('smeta',this)">📋 Smeta</button>
    <button class="tab" onclick="showTab('gedishat',this)">🏗️ Gedişat</button>
    <button class="tab" onclick="showTab('material',this)">📦 Material</button>
    <button class="tab" onclick="showTab('checklist',this)">✅ Yoxlama</button>
    <button class="tab" onclick="showTab('payments',this)">💳 Ödənişlər</button>
  </div>

  <!-- TAB 1: SMETA -->
  <div id="tab-smeta" class="tab-content active">
    {% set ns = namespace(counter=1) %}
    {% for room, categories in rooms.items() %}
    {% set room_total = namespace(val=0) %}
    {% for cat, items in categories.items() %}{% for item in items %}{% set room_total.val = room_total.val + item.qty * item.price %}{% endfor %}{% endfor %}
    {% set progress = progress_data.get(room, {}).get('progress_pct', 0) %}

    <div class="room-section">
      <div class="room-header">
        <span>{{ room }}</span>
        <span class="room-total">{{ "%.2f"|format(room_total.val) }} AZN</span>
      </div>
      <div class="progress-wrap">
        <div class="progress-label"><span>Gedişat</span><span>{{ progress }}%</span></div>
        <div class="progress-track"><div class="progress-fill" style="width:{{ progress }}%"></div></div>
      </div>
      <table class="work-table">
        <thead><tr>
          <th style="width:36px">№</th><th>İşin adı</th>
          <th style="width:70px">Ölçü</th><th style="width:70px">Miqdar</th>
          <th style="width:100px">Qiymət</th><th style="width:110px">Məbləğ</th>
        </tr></thead>
        <tbody>
          {% for cat, items in categories.items() %}
          {% set has_items = [] %}{% for i in items %}{% if i.qty > 0 %}{% set _ = has_items.append(1) %}{% endif %}{% endfor %}
          {% if has_items or items %}
          <tr class="cat-row"><td colspan="6">{{ cat }}</td></tr>
          {% for item in items %}
          <tr class="{{ 'zero-row' if item.qty == 0 else '' }}">
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
          <tr class="room-sub">
            <td colspan="5" style="text-align:right;padding-right:14px">{{ room }} cəmi:</td>
            <td>{{ "%.2f"|format(room_total.val) }} AZN</td>
          </tr>
        </tbody>
      </table>
    </div>
    {% endfor %}

    <div class="totals-card">
      <div class="total-line"><span>İşçilik və işlər</span><span>{{ "%.2f"|format(smeta.total) }} AZN</span></div>
      {% if smeta.discount_pct > 0 %}
      <div class="total-line" style="color:#28a745"><span>Endirim ({{ smeta.discount_pct }}%)</span><span>−{{ "%.2f"|format(smeta.total * smeta.discount_pct / 100) }} AZN</span></div>
      {% endif %}
      <div class="grand-box">
        <div class="lbl">Yekun məbləğ</div>
        <div><span class="amt">{{ "%.2f"|format(smeta.total) }}</span><span class="cur">AZN</span></div>
      </div>
      {% if smeta.notes %}<div class="notes-box">📝 {{ smeta.notes }}</div>{% endif %}
    </div>
  </div>

  <!-- TAB 2: GEDİŞAT -->
  <div id="tab-gedishat" class="tab-content">
    <div class="progress-cards">
      {% for room in rooms %}
      {% set prog = progress_data.get(room, {}) %}
      {% set pct = prog.get('progress_pct', 0) %}
      {% set note = prog.get('notes', '') %}
      <div class="prog-card">
        <h4>{{ room }}</h4>
        <div class="prog-card-bar"><div class="prog-card-fill" style="width:{{ pct }}%"></div></div>
        <div class="prog-pct">{{ pct }}%</div>
        {% if note %}<div class="prog-note">{{ note }}</div>{% endif %}
        {% if pct < 100 and note %}
        <div class="next-step">▶️ Növbəti: {{ note }}</div>
        {% endif %}
      </div>
      {% endfor %}
    </div>

    {% set total_pct = namespace(val=0) %}
    {% for room in rooms %}{% set total_pct.val = total_pct.val + progress_data.get(room, {}).get('progress_pct', 0) %}{% endfor %}
    {% set avg_pct = (total_pct.val / rooms|length) if rooms else 0 %}

    <div class="totals-card" style="margin-top:16px">
      <div class="total-line"><span>Ümumi tamamlanma</span><span style="color:#1B2A4A;font-size:18px;font-weight:700">{{ "%.0f"|format(avg_pct) }}%</span></div>
      <div class="progress-track" style="margin-top:8px;height:10px">
        <div class="progress-fill" style="width:{{ avg_pct }}%;height:100%"></div>
      </div>
    </div>

    {% if photos_by_room %}
    <div class="totals-card" style="margin-top:16px">
      <p style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">📸 Fotolar</p>
      {% for room, photos in photos_by_room.items() %}
      {% if photos %}
      <p style="font-size:12px;font-weight:600;color:#1B2A4A;margin-bottom:6px">{{ room }}</p>
      <div class="photos-grid" style="margin-bottom:12px">
        {% for photo in photos %}
        <div class="photo-item" onclick="openLB('{{ photo.file_id }}')">
          <img src="/photo/{{ photo.file_id }}" alt="" loading="lazy">
        </div>
        {% endfor %}
      </div>
      {% endif %}
      {% endfor %}
    </div>
    {% endif %}
  </div>

  <!-- TAB 3: MATERIALLAR -->
  <div id="tab-material" class="tab-content">
    {% if shopping_list %}
    {% set bought_s = shopping_list|selectattr('status','eq','bought')|list %}
    {% set pending_s = shopping_list|selectattr('status','eq','pending')|list %}
    {% set delivered_s = shopping_list|selectattr('status','eq','delivered')|list %}

    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px">
      <div style="background:#D4EDDA;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#155724">{{ bought_s|length }}</div>
        <div style="font-size:11px;color:#155724">Alınıb ✅</div>
      </div>
      <div style="background:#FFF3CD;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#856404">{{ pending_s|length }}</div>
        <div style="font-size:11px;color:#856404">Gözləyir ⏳</div>
      </div>
      <div style="background:#CCE5FF;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#004085">{{ delivered_s|length }}</div>
        <div style="font-size:11px;color:#004085">Çatdırıldı 🚚</div>
      </div>
    </div>

    {% set urgent_items = shopping_list|selectattr('priority','eq','urgent')|list %}
    {% set normal_items = shopping_list|selectattr('priority','eq','normal')|list %}
    {% set late_items   = shopping_list|selectattr('priority','eq','late')|list %}

    {% for group_label, group_items in [('🔴 TƏCİLİ — 1-ci həftə', urgent_items), ('🟡 Normal — 2-ci həftə', normal_items), ('🟢 Son mərhələ', late_items)] %}
    {% if group_items %}
    <div style="font-size:12px;font-weight:700;color:#1B2A4A;padding:10px 16px;background:#fff;border-radius:8px 8px 0 0;border-bottom:1px solid #F0F2F5;margin-top:12px">{{ group_label }}</div>
    <div class="mat-list" style="border-radius:0 0 8px 8px;margin-top:0">
      {% for mat in group_items %}
      <div class="mat-item">
        <div class="mat-icon {{ 'mat-bought' if mat.status == 'bought' else ('mat-missing' if mat.status == 'delivered' else 'mat-pending') }}">
          {{ '✅' if mat.status == 'bought' else ('🚚' if mat.status == 'delivered' else '⏳') }}
        </div>
        <div class="mat-info">
          <div class="mat-name">{{ mat.item_name }}</div>
          <div class="mat-detail">{{ mat.qty }} {{ mat.unit }}{% if mat.notes %} · {{ mat.notes }}{% endif %}</div>
        </div>
        <span class="mat-status {{ 'st-bought' if mat.status == 'bought' else ('st-missing' if mat.status == 'delivered' else 'st-pending') }}">
          {{ 'Alındı' if mat.status == 'bought' else ('Çatdırıldı' if mat.status == 'delivered' else 'Gözləyir') }}
        </span>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    {% endfor %}

    {% else %}
    {% if materials %}
    {% set bought = materials|selectattr('status','eq','bought')|list %}
    {% set pending = materials|selectattr('status','eq','pending')|list %}
    {% set delivered = materials|selectattr('status','eq','delivered')|list %}
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px">
      <div style="background:#D4EDDA;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#155724">{{ bought|length }}</div>
        <div style="font-size:11px;color:#155724">Alınıb</div>
      </div>
      <div style="background:#FFF3CD;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#856404">{{ pending|length }}</div>
        <div style="font-size:11px;color:#856404">Gözləyir</div>
      </div>
      <div style="background:#F8D7DA;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#721C24">{{ delivered|length }}</div>
        <div style="font-size:11px;color:#721C24">Çatdırılıb</div>
      </div>
    </div>
    <div class="mat-list">
      {% for mat in materials %}
      <div class="mat-item">
        <div class="mat-icon {{ 'mat-bought' if mat.status == 'bought' else ('mat-pending' if mat.status == 'pending' else 'mat-missing') }}">
          {{ '✅' if mat.status == 'bought' else ('⏳' if mat.status == 'pending' else '🚚') }}
        </div>
        <div class="mat-info">
          <div class="mat-name">{{ mat.name }}</div>
          <div class="mat-detail">{{ mat.qty_needed }} {{ mat.unit }}{% if mat.notes %} · {{ mat.notes }}{% endif %}</div>
        </div>
        <span class="mat-status {{ 'st-bought' if mat.status == 'bought' else ('st-pending' if mat.status == 'pending' else 'st-missing') }}">
          {{ 'Alındı' if mat.status == 'bought' else ('Gözləyir' if mat.status == 'pending' else 'Çatdırıldı') }}
        </span>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="mat-empty">
      <div style="font-size:40px;margin-bottom:12px">📦</div>
      <p>Hələ material əlavə edilməyib</p>
      <p style="margin-top:6px;font-size:11px">Bot vasitəsilə material əlavə edin</p>
    </div>
    {% endif %}
    {% endif %}
  </div>

  <!-- TAB 4: YOXLAMA -->
  <div id="tab-checklist" class="tab-content">
    {% if checklist_by_room %}
    {% set total_items = namespace(val=0) %}
    {% set checked_items = namespace(val=0) %}
    {% for room, items in checklist_by_room.items() %}
    {% for item in items %}
    {% set total_items.val = total_items.val + 1 %}
    {% if item.is_checked %}{% set checked_items.val = checked_items.val + 1 %}{% endif %}
    {% endfor %}
    {% endfor %}

    <div style="background:#fff;border-radius:10px;padding:16px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:13px;color:#666">Yoxlanılıb</span>
        <span style="font-size:18px;font-weight:700;color:#1B2A4A">{{ checked_items.val }}/{{ total_items.val }}</span>
      </div>
      <div class="progress-track" style="margin-top:8px;height:8px">
        <div class="progress-fill" style="width:{{ (checked_items.val / total_items.val * 100) if total_items.val > 0 else 0 }}%;height:100%"></div>
      </div>
    </div>

    {% for room, items in checklist_by_room.items() %}
    <div class="check-room">
      <div class="check-room-title">🏠 {{ room }}</div>
      <div class="check-items">
        {% for item in items %}
        <div class="check-item">
          <div class="check-box {{ 'checked' if item.is_checked else 'unchecked' }}">
            {{ '✓' if item.is_checked else '' }}
          </div>
          <div style="flex:1">
            <div class="check-text {{ 'done' if item.is_checked else '' }}">{{ item.item }}</div>
            {% if item.is_checked and item.checked_at %}
            <div class="check-meta">{{ item.checked_at[:10] }}{% if item.notes %} · {{ item.notes }}{% endif %}</div>
            {% endif %}
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
    {% else %}
    <div class="mat-empty">
      <div style="font-size:40px;margin-bottom:12px">✅</div>
      <p>Hələ check-list əlavə edilməyib</p>
    </div>
    {% endif %}
  </div>

  <!-- TAB 5: ÖDƏNİŞLƏR -->
  <div id="tab-payments" class="tab-content">
    {% if payments %}
    {% set total_paid_amt = namespace(val=0) %}
    {% for p in payments %}{% set total_paid_amt.val = total_paid_amt.val + p.amount %}{% endfor %}
    {% set pct = (total_paid_amt.val / smeta.total * 100) if smeta.total > 0 else 0 %}

    <div class="pay-summary">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:13px;color:#666">Ödənilən məbləğ</span>
        <span style="font-size:18px;font-weight:700;color:#1B2A4A">{{ "%.2f"|format(total_paid_amt.val) }} AZN</span>
      </div>
      <div class="pay-bar-wrap">
        <div class="pay-bar-fill" style="width:{{ [pct,100]|min }}%"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:#888">
        <span>Ödənilib: {{ "%.2f"|format(total_paid_amt.val) }} AZN</span>
        <span>Ümumi: {{ "%.2f"|format(smeta.total) }} AZN ({{ "%.0f"|format(pct) }}%)</span>
      </div>
      {% set remaining = smeta.total - total_paid_amt.val %}
      {% if remaining > 0 %}
      <div style="margin-top:10px;padding:10px 14px;background:#FFF3CD;border-radius:8px;font-size:12px;color:#856404">
        ⏳ Qalıq: <strong>{{ "%.2f"|format(remaining) }} AZN</strong>
      </div>
      {% else %}
      <div style="margin-top:10px;padding:10px 14px;background:#D4EDDA;border-radius:8px;font-size:12px;color:#155724">
        ✅ Tam ödənilib
      </div>
      {% endif %}
    </div>

    <div class="pay-list">
      {% for p in payments %}
      {% set ptype_map = {'advance':'💰 Avans','interim':'💵 Ara ödəniş','final':'✅ Son ödəniş'} %}
      <div class="pay-item">
        <div class="pay-icon">💳</div>
        <div class="pay-info">
          <div class="pay-amount">{{ "%.2f"|format(p.amount) }} AZN</div>
          <div class="pay-type">{{ ptype_map.get(p.payment_type, p.payment_type) }}</div>
          <div class="pay-cats">
            {% if p.material_amount > 0 %}<span class="pay-cat">📦 Material</span>{% endif %}
            {% if p.labor_amount > 0 %}<span class="pay-cat">👷 İşçilik</span>{% endif %}
            {% if p.other_amount > 0 %}<span class="pay-cat">📋 Digər</span>{% endif %}
          </div>
          {% if p.notes %}<div style="font-size:11px;color:#888;margin-top:4px">{{ p.notes }}</div>{% endif %}
        </div>
        <div class="pay-date">{{ p.created_at[:10] }}</div>
      </div>
      {% endfor %}
    </div>

    {% else %}
    <div class="mat-empty">
      <div style="font-size:40px;margin-bottom:12px">💳</div>
      <p>Hələ ödəniş qeyd edilməyib</p>
    </div>
    {% endif %}
  </div>

  <div class="footer">
    <p>Bu smeta <strong>Zari Design</strong> tərəfindən hazırlanmışdır</p>
    <p style="margin-top:3px">+994 50 444 09 00 · 3 Mərkəzi bulvar küçəsi, Bakı</p>
  </div>

</div>

<div class="lightbox" id="lb" onclick="closeLB()">
  <span class="lb-close">×</span>
  <img id="lb-img" src="" alt="">
</div>

<script>
function showTab(name, el) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  el.classList.add('active');
}
function openLB(id) {
  document.getElementById('lb-img').src = '/photo/' + id;
  document.getElementById('lb').classList.add('open');
}
function closeLB() { document.getElementById('lb').classList.remove('open'); }
</script>

</body>
</html>"""


async def get_data_async(smeta_number):
    from database import get_pool
    pool = await get_pool()
    result = {}

    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT * FROM smetas WHERE smeta_number=$1", smeta_number
        )
        if not row:
            return None
        d = dict(row)
        d["rooms_data"] = json.loads(d["rooms_data"])
        result["smeta"] = d

        progress = {}
        try:
            rows = await db.fetch(
                "SELECT * FROM room_progress WHERE smeta_number=$1", smeta_number
            )
            for r in rows:
                rd = dict(r)
                progress[rd["room_name"]] = rd
        except Exception:
            pass
        result["progress"] = progress

        photos_by_room = {}
        try:
            rows = await db.fetch(
                "SELECT * FROM smeta_photos WHERE smeta_number=$1 ORDER BY created_at DESC",
                smeta_number
            )
            for r in rows:
                p = dict(r)
                room = p.get("room_name", "Ümumi")
                photos_by_room.setdefault(room, []).append(p)
        except Exception:
            pass
        result["photos_by_room"] = photos_by_room

        try:
            rows = await db.fetch(
                "SELECT * FROM materials WHERE smeta_number=$1 ORDER BY created_at",
                smeta_number
            )
            result["materials"] = [dict(r) for r in rows]
        except Exception:
            result["materials"] = []

        checklist_by_room = {}
        try:
            rows = await db.fetch(
                "SELECT * FROM checklist WHERE smeta_number=$1 ORDER BY room_name, created_at",
                smeta_number
            )
            for r in rows:
                item = dict(r)
                room = item.get("room_name", "Ümumi")
                checklist_by_room.setdefault(room, []).append(item)
        except Exception:
            pass
        result["checklist_by_room"] = checklist_by_room

        try:
            rows = await db.fetch(
                "SELECT * FROM payments WHERE smeta_number=$1 ORDER BY created_at DESC",
                smeta_number
            )
            result["payments"] = [dict(r) for r in rows]
        except Exception:
            result["payments"] = []

        try:
            rows = await db.fetch(
                "SELECT * FROM shopping_list WHERE smeta_number=$1 ORDER BY priority, created_at",
                smeta_number
            )
            result["shopping_list"] = [dict(r) for r in rows]
        except Exception:
            result["shopping_list"] = []

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
        photos_by_room=data["photos_by_room"],
        materials=data["materials"],
        checklist_by_room=data["checklist_by_room"],
        payments=data["payments"],
        shopping_list=data["shopping_list"],
    )


@app.route("/photo/<file_id>")
def get_photo(file_id):
    bot_token = os.getenv("BOT_TOKEN", "")
    try:
        r = req_lib.get(f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}", timeout=5)
        file_path = r.json()["result"]["file_path"]
        photo = req_lib.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}", timeout=10)
        return Response(photo.content, mimetype="image/jpeg")
    except Exception:
        return "", 404


@app.route("/")
def index():
    return "<div style='font-family:Arial;text-align:center;padding:80px'><h1 style='color:#1B2A4A'>Zari Design</h1><p style='color:#C9973A'>Təmir Smeta Sistemi</p></div>", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
