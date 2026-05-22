"""
PartSelect Database Inspector
Run: python inspector.py
Opens at http://localhost:5050
"""

import json
import re
import math
from pathlib import Path
from collections import defaultdict, Counter

from flask import Flask, render_template_string, request, jsonify, redirect, url_for

app = Flask(__name__)

DATA_DIR     = Path("data")
PARTS_FILE   = DATA_DIR / "parts_raw.json"
MAP_FILE     = DATA_DIR / "model_part_map.json"
SITEMAP_FILE = DATA_DIR / "sitemap_parts.json"

# ── Data loading (cached in-process) ─────────────────────────────────────────

_parts:        list[dict] = []
_model_map:    dict       = {}
_sitemap:      list[dict] = []
_parts_index:  dict       = {}
_repairs:      list[dict] = []
_blogs:        list[dict] = []
_symptom_map:  dict       = {}
_part_type_map:dict       = {}
_rel_summary:  dict       = {}

def load_data():
    global _parts, _model_map, _sitemap, _parts_index
    global _repairs, _blogs, _symptom_map, _part_type_map, _rel_summary
    if PARTS_FILE.exists():
        _parts = json.loads(PARTS_FILE.read_text(encoding="utf-8", errors="replace"))
        _parts = [p for p in _parts if p.get("part_number")]
        _parts_index = {p["part_number"]: p for p in _parts}
    if MAP_FILE.exists():
        _model_map = json.loads(MAP_FILE.read_text(encoding="utf-8", errors="replace"))
    if SITEMAP_FILE.exists():
        _sitemap = json.loads(SITEMAP_FILE.read_text(encoding="utf-8", errors="replace"))
    for fname, var_name in [
        ("repairs.json", "_repairs"),
        ("blogs.json",   "_blogs"),
        ("symptom_part_map.json", "_symptom_map"),
        ("part_type_map.json",    "_part_type_map"),
        ("relational_summary.json", "_rel_summary"),
    ]:
        p = DATA_DIR / fname
        if p.exists():
            globals()[var_name] = json.loads(p.read_text(encoding="utf-8", errors="replace"))

def reload_data():
    load_data()


# ── Base template ─────────────────────────────────────────────────────────────

BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PartSelect DB Inspector</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background:#f8f9fa; font-size:.93rem; }
  .navbar { background:#1b3875 !important; }
  .navbar-brand,.nav-link { color:#fff !important; }
  .nav-link:hover { color:#ffa500 !important; }
  .nav-link.active { color:#ffa500 !important; font-weight:600; }
  .card { border:none; box-shadow:0 1px 4px rgba(0,0,0,.08); }
  .stat-card { border-left:4px solid #1b3875; }
  .stat-num  { font-size:2rem; font-weight:700; color:#1b3875; }
  .badge-fridge { background:#0d6efd; }
  .badge-dish   { background:#198754; }
  pre { background:#f1f3f5; border-radius:6px; padding:12px; font-size:.82rem; }
  .table-hover tbody tr:hover { background:#eef2ff; }
  .quality-bar { height:8px; border-radius:4px; }
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg mb-4">
  <div class="container-fluid">
    <a class="navbar-brand fw-bold" href="/">PartSelect Inspector</a>
    <div class="navbar-nav">
      <a class="nav-link {% if page=='dashboard' %}active{% endif %}" href="/">Dashboard</a>
      <a class="nav-link {% if page=='parts' %}active{% endif %}" href="/parts">Parts</a>
      <a class="nav-link {% if page=='models' %}active{% endif %}" href="/models">Models</a>
      <a class="nav-link {% if page=='search' %}active{% endif %}" href="/search">Semantic Search</a>
      <a class="nav-link {% if page=='quality' %}active{% endif %}" href="/quality">Data Quality</a>
      <a class="nav-link {% if page=='repairs' %}active{% endif %}" href="/repairs">Repairs</a>
      <a class="nav-link {% if page=='blogs' %}active{% endif %}" href="/blogs">Blogs</a>
      <a class="nav-link {% if page=='relations' %}active{% endif %}" href="/relations">Relations</a>
    </div>
    <span class="text-white-50 ms-auto small">
      {{ parts_count }} parts &nbsp;|&nbsp; {{ model_count }} models
    </span>
  </div>
</nav>
<div class="container-fluid px-4">
{% block content %}{% endblock %}
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""


def render(template, **kwargs):
    kwargs.setdefault("parts_count", len(_parts))
    kwargs.setdefault("model_count", len(_model_map))
    full = BASE.replace("{% block content %}{% endblock %}", template)
    return render_template_string(full, **kwargs)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    fridge = [p for p in _parts if p.get("category") == "refrigerator"]
    dish   = [p for p in _parts if p.get("category") == "dishwasher"]

    brands = Counter(p.get("brand","") for p in _parts if p.get("brand"))
    top_brands = brands.most_common(10)

    rated  = [p for p in _parts if p.get("rating", 0) > 0]
    priced = [p for p in _parts if p.get("price", 0) > 0]
    sympd  = [p for p in _parts if p.get("symptoms")]
    compat = [p for p in _parts if p.get("compatible_models")]

    avg_rating = round(sum(p["rating"] for p in rated) / len(rated), 2) if rated else 0
    avg_price  = round(sum(p["price"]  for p in priced) / len(priced), 2) if priced else 0

    sitemap_n = len(_sitemap)

    tpl = """
<div class="row g-3 mb-4">
  <div class="col-md-3">
    <div class="card stat-card p-3">
      <div class="text-muted small">Total Scraped Parts</div>
      <div class="stat-num">{{ total }}</div>
      <small class="text-muted">of {{ sitemap_n }} in sitemap</small>
    </div>
  </div>
  <div class="col-md-3">
    <div class="card stat-card p-3" style="border-color:#0d6efd">
      <div class="text-muted small">Refrigerator</div>
      <div class="stat-num" style="color:#0d6efd">{{ fridge_n }}</div>
      <small class="text-muted">{{ "%.1f"|format(fridge_n/total*100 if total else 0) }}% of scraped</small>
    </div>
  </div>
  <div class="col-md-3">
    <div class="card stat-card p-3" style="border-color:#198754">
      <div class="text-muted small">Dishwasher</div>
      <div class="stat-num" style="color:#198754">{{ dish_n }}</div>
      <small class="text-muted">{{ "%.1f"|format(dish_n/total*100 if total else 0) }}% of scraped</small>
    </div>
  </div>
  <div class="col-md-3">
    <div class="card stat-card p-3" style="border-color:#fd7e14">
      <div class="text-muted small">Models Mapped</div>
      <div class="stat-num" style="color:#fd7e14">{{ model_count }}</div>
      <small class="text-muted">from 287k in sitemap</small>
    </div>
  </div>
</div>

<div class="row g-3 mb-4">
  <div class="col-md-3">
    <div class="card p-3 text-center">
      <div class="text-muted small">Avg Rating</div>
      <div class="fs-3 fw-bold text-warning">{{ avg_rating }} ★</div>
      <small class="text-muted">{{ rated_n }} parts rated</small>
    </div>
  </div>
  <div class="col-md-3">
    <div class="card p-3 text-center">
      <div class="text-muted small">Avg Price</div>
      <div class="fs-3 fw-bold text-success">${{ avg_price }}</div>
      <small class="text-muted">{{ priced_n }} parts priced</small>
    </div>
  </div>
  <div class="col-md-3">
    <div class="card p-3 text-center">
      <div class="text-muted small">With Symptoms</div>
      <div class="fs-3 fw-bold text-primary">{{ sympd_n }}</div>
      <small class="text-muted">{{ "%.0f"|format(sympd_n/total*100 if total else 0) }}%</small>
    </div>
  </div>
  <div class="col-md-3">
    <div class="card p-3 text-center">
      <div class="text-muted small">With Model Links</div>
      <div class="fs-3 fw-bold text-info">{{ compat_n }}</div>
      <small class="text-muted">{{ "%.0f"|format(compat_n/total*100 if total else 0) }}%</small>
    </div>
  </div>
</div>

<div class="row g-3">
  <div class="col-md-6">
    <div class="card p-3">
      <h6 class="mb-3">Top Brands</h6>
      {% for brand, count in top_brands %}
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span>{{ brand }}</span>
        <span class="badge bg-secondary">{{ count }}</span>
      </div>
      {% endfor %}
    </div>
  </div>
  <div class="col-md-6">
    <div class="card p-3">
      <h6 class="mb-3">Scraping Progress</h6>
      <div class="mb-2">
        <div class="d-flex justify-content-between small mb-1">
          <span>Scraped</span><span>{{ total }} / {{ sitemap_n }}</span>
        </div>
        <div class="progress" style="height:10px">
          <div class="progress-bar bg-success" style="width:{{ "%.1f"|format(total/sitemap_n*100 if sitemap_n else 0) }}%"></div>
        </div>
      </div>
      <small class="text-muted">Refresh page after scrape_parts.py runs to see updated counts.</small>
      <div class="mt-3">
        <a href="/reload" class="btn btn-sm btn-outline-secondary">Reload data</a>
      </div>
    </div>
  </div>
</div>
"""
    return render(tpl, page="dashboard",
                  total=len(_parts), sitemap_n=sitemap_n,
                  fridge_n=len(fridge), dish_n=len(dish),
                  avg_rating=avg_rating, avg_price=avg_price,
                  rated_n=len(rated), priced_n=len(priced),
                  sympd_n=len(sympd), compat_n=len(compat),
                  top_brands=top_brands)


# ── Parts browser ─────────────────────────────────────────────────────────────

PAGE_SIZE = 50

@app.route("/parts")
def parts_browser():
    q        = request.args.get("q", "").strip().lower()
    cat      = request.args.get("cat", "")
    brand    = request.args.get("brand", "")
    sort     = request.args.get("sort", "review_count")
    page     = max(1, int(request.args.get("page", 1)))

    filtered = _parts
    if q:
        filtered = [p for p in filtered
                    if q in (p.get("name","") + p.get("description","") +
                              p.get("part_number","")).lower()]
    if cat:
        filtered = [p for p in filtered if p.get("category") == cat]
    if brand:
        filtered = [p for p in filtered if p.get("brand","").lower() == brand.lower()]

    reverse = sort in ("review_count", "rating", "price")
    try:
        filtered.sort(key=lambda p: p.get(sort, 0) or 0, reverse=reverse)
    except Exception:
        pass

    total_pages = max(1, math.ceil(len(filtered) / PAGE_SIZE))
    page = min(page, total_pages)
    slice_ = filtered[(page-1)*PAGE_SIZE : page*PAGE_SIZE]

    brands_all = sorted(set(p.get("brand","") for p in _parts if p.get("brand")))

    tpl = """
<div class="row mb-3">
  <div class="col">
    <form method="get" class="row g-2">
      <div class="col-md-4">
        <input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Search name, description, part#...">
      </div>
      <div class="col-md-2">
        <select name="cat" class="form-select form-select-sm">
          <option value="">All categories</option>
          <option {% if cat=='refrigerator' %}selected{% endif %} value="refrigerator">Refrigerator</option>
          <option {% if cat=='dishwasher' %}selected{% endif %} value="dishwasher">Dishwasher</option>
        </select>
      </div>
      <div class="col-md-2">
        <select name="brand" class="form-select form-select-sm">
          <option value="">All brands</option>
          {% for b in brands_all %}
          <option {% if brand==b %}selected{% endif %} value="{{ b }}">{{ b }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-2">
        <select name="sort" class="form-select form-select-sm">
          <option {% if sort=='review_count' %}selected{% endif %} value="review_count">Most reviewed</option>
          <option {% if sort=='rating' %}selected{% endif %} value="rating">Highest rated</option>
          <option {% if sort=='price' %}selected{% endif %} value="price">Price</option>
          <option {% if sort=='name' %}selected{% endif %} value="name">Name</option>
        </select>
      </div>
      <div class="col-md-1">
        <button class="btn btn-sm btn-primary w-100">Filter</button>
      </div>
      <div class="col-md-1">
        <a href="/parts" class="btn btn-sm btn-outline-secondary w-100">Clear</a>
      </div>
    </form>
  </div>
</div>

<div class="d-flex justify-content-between align-items-center mb-2">
  <small class="text-muted">{{ filtered_n }} results &nbsp; page {{ cur_page }} of {{ total_pages }}</small>
</div>

<div class="card">
<table class="table table-hover table-sm mb-0">
  <thead class="table-light">
    <tr>
      <th>Part #</th><th>Name</th><th>Category</th><th>Brand</th>
      <th>Price</th><th>Rating</th><th>Reviews</th><th>Symptoms</th><th>Models</th>
    </tr>
  </thead>
  <tbody>
  {% for p in parts %}
  <tr>
    <td><a href="/part/{{ p.part_number }}">{{ p.part_number }}</a></td>
    <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
        title="{{ p.name }}">{{ p.name }}</td>
    <td>
      {% if p.category=='refrigerator' %}
        <span class="badge badge-fridge">fridge</span>
      {% else %}
        <span class="badge badge-dish">dish</span>
      {% endif %}
    </td>
    <td>{{ p.brand }}</td>
    <td>{% if p.price %}${{ "%.2f"|format(p.price) }}{% else %}<span class="text-muted">—</span>{% endif %}</td>
    <td>{% if p.rating %}{{ "%.1f"|format(p.rating) }}★{% else %}<span class="text-muted">—</span>{% endif %}</td>
    <td>{{ p.review_count or '' }}</td>
    <td>{{ p.symptoms|length }}</td>
    <td>{{ (p.compatible_models or [])|length }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>

<nav class="mt-3">
  <ul class="pagination pagination-sm">
    {% if cur_page > 1 %}
    <li class="page-item"><a class="page-link" href="?q={{ q }}&cat={{ cat }}&brand={{ brand }}&sort={{ sort }}&page={{ cur_page-1 }}">Prev</a></li>
    {% endif %}
    {% for p in range([1, cur_page-2]|max, [total_pages+1, cur_page+3]|min) %}
    <li class="page-item {% if p==cur_page %}active{% endif %}">
      <a class="page-link" href="?q={{ q }}&cat={{ cat }}&brand={{ brand }}&sort={{ sort }}&page={{ p }}">{{ p }}</a>
    </li>
    {% endfor %}
    {% if cur_page < total_pages %}
    <li class="page-item"><a class="page-link" href="?q={{ q }}&cat={{ cat }}&brand={{ brand }}&sort={{ sort }}&page={{ cur_page+1 }}">Next</a></li>
    {% endif %}
  </ul>
</nav>
"""
    return render(tpl, page="parts",
                  q=q, cat=cat, brand=brand, sort=sort,
                  parts=slice_, filtered_n=len(filtered),
                  total_pages=total_pages, cur_page=page,
                  brands_all=brands_all)


# ── Part detail ───────────────────────────────────────────────────────────────

@app.route("/part/<part_number>")
def part_detail(part_number):
    p = _parts_index.get(part_number)
    if not p:
        return f"<h3>Part {part_number} not found</h3><a href='/parts'>Back</a>", 404

    tpl = """
<div class="row">
  <div class="col-md-8">
    <div class="card p-4">
      <div class="d-flex justify-content-between align-items-start mb-3">
        <div>
          <h4 class="mb-1">{{ p.name }}</h4>
          <span class="text-muted">{{ p.part_number }}</span>
          {% if p.mpn %} &nbsp;·&nbsp; <span class="text-muted">MPN: {{ p.mpn }}</span>{% endif %}
        </div>
        <div class="text-end">
          {% if p.price %}<div class="fs-4 fw-bold text-success">${{ "%.2f"|format(p.price) }}</div>{% endif %}
          {% if p.rating %}<div class="text-warning">{{ "%.1f"|format(p.rating) }} ★ ({{ p.review_count }} reviews)</div>{% endif %}
        </div>
      </div>

      <div class="mb-3">
        {% if p.category=='refrigerator' %}
          <span class="badge badge-fridge me-1">Refrigerator</span>
        {% else %}
          <span class="badge badge-dish me-1">Dishwasher</span>
        {% endif %}
        {% if p.brand %}<span class="badge bg-secondary me-1">{{ p.brand }}</span>{% endif %}
        {% if p.availability %}<span class="badge bg-light text-dark border">{{ p.availability }}</span>{% endif %}
      </div>

      {% if p.description %}
      <p class="text-muted">{{ p.description }}</p>
      {% endif %}

      {% if p.symptoms %}
      <div class="mb-3">
        <h6>Fixes these symptoms:</h6>
        <ul class="mb-0">{% for s in p.symptoms %}<li>{{ s }}</li>{% endfor %}</ul>
      </div>
      {% endif %}

      <div class="row g-2 mb-3">
        {% if p.install_difficulty %}
        <div class="col-auto">
          <span class="badge bg-light text-dark border">Difficulty: {{ p.install_difficulty }}</span>
        </div>
        {% endif %}
        {% if p.install_time %}
        <div class="col-auto">
          <span class="badge bg-light text-dark border">Time: {{ p.install_time }}</span>
        </div>
        {% endif %}
      </div>

      {% if p.replaces %}
      <div class="mb-3">
        <small class="text-muted">Replaces: {{ p.replaces | join(", ") }}</small>
      </div>
      {% endif %}

      <div class="d-flex gap-2 mt-2">
        <a href="{{ p.url }}" target="_blank" class="btn btn-sm btn-primary">View on PartSelect</a>
        {% if p.video_url %}
        <a href="{{ p.video_url }}" target="_blank" class="btn btn-sm btn-outline-danger">Watch Video</a>
        {% endif %}
        <a href="/parts" class="btn btn-sm btn-outline-secondary">Back</a>
      </div>
    </div>
  </div>

  <div class="col-md-4">
    <div class="card p-3 mb-3">
      <h6>Compatible Models ({{ (p.compatible_models or []) | length }})</h6>
      {% if p.compatible_models %}
      <div style="max-height:300px;overflow-y:auto">
        {% for mn in p.compatible_models %}
        <a href="/model/{{ mn }}" class="badge bg-light text-dark border me-1 mb-1 text-decoration-none">{{ mn }}</a>
        {% endfor %}
      </div>
      {% else %}
      <small class="text-muted">None scraped</small>
      {% endif %}
    </div>

    <div class="card p-3">
      <h6>Raw JSON</h6>
      <pre style="max-height:350px;overflow:auto;font-size:.75rem">{{ p_json }}</pre>
    </div>
  </div>
</div>
"""
    return render(tpl, page="parts", p=p,
                  p_json=json.dumps({k: v for k, v in p.items() if k != "_source"}, indent=2))


# ── Model lookup ──────────────────────────────────────────────────────────────

@app.route("/models")
def models_browser():
    q    = request.args.get("q", "").strip().upper()
    page = max(1, int(request.args.get("page", 1)))

    if q:
        keys = [k for k in _model_map if q in k]
    else:
        keys = list(_model_map.keys())

    total_pages = max(1, math.ceil(len(keys) / PAGE_SIZE))
    page = min(page, total_pages)
    slice_ = keys[(page-1)*PAGE_SIZE : page*PAGE_SIZE]

    tpl = """
<div class="row mb-3">
  <div class="col-md-4">
    <form method="get" class="d-flex gap-2">
      <input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Model number search...">
      <button class="btn btn-sm btn-primary">Search</button>
      <a href="/models" class="btn btn-sm btn-outline-secondary">Clear</a>
    </form>
  </div>
  <div class="col text-muted small d-flex align-items-center">
    {{ total }} models mapped &nbsp;|&nbsp; page {{ cur_page }} of {{ total_pages }}
  </div>
</div>

<div class="card">
<table class="table table-hover table-sm mb-0">
  <thead class="table-light">
    <tr><th>Model Number</th><th>Category</th><th>Parts</th><th></th></tr>
  </thead>
  <tbody>
  {% for mn in models %}
    {% set entry = model_map[mn] %}
    <tr>
      <td><a href="/model/{{ mn }}">{{ mn }}</a></td>
      <td>
        {% if entry.category=='refrigerator' %}
          <span class="badge badge-fridge">fridge</span>
        {% else %}
          <span class="badge badge-dish">dish</span>
        {% endif %}
      </td>
      <td>{{ entry.parts | length }}</td>
      <td><a href="https://www.partselect.com/Models/{{ mn }}/" target="_blank" class="text-muted small">PartSelect ↗</a></td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>

<nav class="mt-3">
  <ul class="pagination pagination-sm">
    {% if cur_page > 1 %}
    <li class="page-item"><a class="page-link" href="?q={{ q }}&page={{ cur_page-1 }}">Prev</a></li>
    {% endif %}
    {% for p in range([1, cur_page-2]|max, [total_pages+1, cur_page+3]|min) %}
    <li class="page-item {% if p==cur_page %}active{% endif %}">
      <a class="page-link" href="?q={{ q }}&page={{ p }}">{{ p }}</a>
    </li>
    {% endfor %}
    {% if cur_page < total_pages %}
    <li class="page-item"><a class="page-link" href="?q={{ q }}&page={{ cur_page+1 }}">Next</a></li>
    {% endif %}
  </ul>
</nav>
"""
    return render(tpl, page="models",
                  q=q, models=slice_, model_map=_model_map,
                  total=len(keys), total_pages=total_pages, cur_page=page)


@app.route("/model/<model_number>")
def model_detail(model_number):
    mn    = model_number.upper()
    entry = _model_map.get(mn)
    if not entry:
        tpl = """<div class="alert alert-warning">Model <strong>{{ mn }}</strong> not in local map.
          <a href="https://www.partselect.com/Models/{{ mn }}/" target="_blank">Check on PartSelect</a>
          &nbsp;|&nbsp; <a href="/models">Back</a>
        </div>"""
        return render(tpl, page="models", mn=mn)

    parts = [_parts_index[pn] for pn in entry.get("parts", []) if pn in _parts_index]
    missing_pns = [pn for pn in entry.get("parts", []) if pn not in _parts_index]

    tpl = """
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h4 class="mb-0">Model {{ mn }}</h4>
    <span class="badge {% if entry.category=='refrigerator' %}badge-fridge{% else %}badge-dish{% endif %}">
      {{ entry.category }}
    </span>
  </div>
  <div class="d-flex gap-2">
    <a href="https://www.partselect.com/Models/{{ mn }}/" target="_blank" class="btn btn-sm btn-primary">View on PartSelect</a>
    <a href="/models" class="btn btn-sm btn-outline-secondary">Back</a>
  </div>
</div>

<div class="row mb-3 g-3">
  <div class="col-auto">
    <div class="card px-3 py-2 text-center">
      <div class="stat-num" style="font-size:1.6rem">{{ entry.parts|length }}</div>
      <small class="text-muted">Part numbers mapped</small>
    </div>
  </div>
  <div class="col-auto">
    <div class="card px-3 py-2 text-center">
      <div class="stat-num" style="font-size:1.6rem;color:#198754">{{ parts|length }}</div>
      <small class="text-muted">Parts with full data</small>
    </div>
  </div>
  {% if missing_pns %}
  <div class="col-auto">
    <div class="card px-3 py-2 text-center">
      <div class="stat-num" style="font-size:1.6rem;color:#dc3545">{{ missing_pns|length }}</div>
      <small class="text-muted">Parts not yet scraped</small>
    </div>
  </div>
  {% endif %}
</div>

{% if parts %}
<div class="card mb-3">
<table class="table table-hover table-sm mb-0">
  <thead class="table-light">
    <tr><th>Part #</th><th>Name</th><th>Price</th><th>Rating</th><th>Symptoms</th></tr>
  </thead>
  <tbody>
  {% for p in parts %}
  <tr>
    <td><a href="/part/{{ p.part_number }}">{{ p.part_number }}</a></td>
    <td>{{ p.name }}</td>
    <td>{% if p.price %}${{ "%.2f"|format(p.price) }}{% else %}—{% endif %}</td>
    <td>{% if p.rating %}{{ "%.1f"|format(p.rating) }}★{% else %}—{% endif %}</td>
    <td>{{ (p.symptoms or [])|length }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endif %}

{% if missing_pns %}
<div class="card p-3">
  <h6 class="text-muted">Not yet scraped ({{ missing_pns|length }})</h6>
  <div>
    {% for pn in missing_pns %}
    <span class="badge bg-light text-dark border me-1 mb-1">{{ pn }}</span>
    {% endfor %}
  </div>
</div>
{% endif %}
"""
    return render(tpl, page="models",
                  mn=mn, entry=entry, parts=parts, missing_pns=missing_pns)


# ── Semantic search ───────────────────────────────────────────────────────────

_faiss_loaded = False
_faiss_index  = None
_faiss_meta   = None
_st_model     = None

def _try_load_faiss():
    global _faiss_loaded, _faiss_index, _faiss_meta, _st_model
    if _faiss_loaded:
        return _faiss_index is not None
    _faiss_loaded = True
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
        import numpy as np
        meta_path  = Path("../backend/app/data/parts_metadata.json")
        index_path = Path("../backend/app/data/faiss_index.bin")
        if not meta_path.exists() or not index_path.exists():
            return False
        _faiss_index = faiss.read_index(str(index_path))
        _faiss_meta  = json.loads(meta_path.read_text(encoding="utf-8"))
        _st_model    = SentenceTransformer("all-MiniLM-L6-v2")
        return True
    except Exception as e:
        print(f"[inspector] FAISS load failed: {e}")
        return False


@app.route("/search")
def semantic_search():
    q       = request.args.get("q", "").strip()
    cat     = request.args.get("cat", "")
    results = []
    error   = None
    faiss_ok = _try_load_faiss()

    if q and faiss_ok:
        try:
            import numpy as np
            q_vec = _st_model.encode([q], normalize_embeddings=True).astype(np.float32)
            k = min(20, _faiss_index.ntotal)
            scores, idxs = _faiss_index.search(q_vec, k)
            for score, idx in zip(scores[0], idxs[0]):
                if idx < 0 or idx >= len(_faiss_meta):
                    continue
                item = _faiss_meta[idx]
                if not item.get("part_number"):
                    continue
                if cat and item.get("category") != cat:
                    continue
                results.append({"score": float(score), **item})
                if len(results) >= 10:
                    break
        except Exception as e:
            error = str(e)
    elif q and not faiss_ok:
        error = "FAISS index not available. Run embed_and_index.py first."

    tpl = """
<div class="row mb-3">
  <div class="col-md-7">
    <form method="get" class="d-flex gap-2">
      <input name="q" value="{{ q }}" class="form-control" placeholder="e.g. ice maker not working, dishwasher not draining...">
      <select name="cat" class="form-select" style="max-width:160px">
        <option value="">All</option>
        <option {% if cat=='refrigerator' %}selected{% endif %} value="refrigerator">Refrigerator</option>
        <option {% if cat=='dishwasher' %}selected{% endif %} value="dishwasher">Dishwasher</option>
      </select>
      <button class="btn btn-primary">Search</button>
    </form>
  </div>
</div>

{% if error %}
<div class="alert alert-warning">{{ error }}</div>
{% endif %}

{% if not faiss_ok and not error %}
<div class="alert alert-info">
  Run <code>python embed_and_index.py</code> to enable semantic search.
</div>
{% endif %}

{% if results %}
<div class="card">
<table class="table table-hover mb-0">
  <thead class="table-light">
    <tr><th>Score</th><th>Part #</th><th>Name</th><th>Category</th><th>Brand</th><th>Price</th></tr>
  </thead>
  <tbody>
  {% for r in results %}
  <tr>
    <td><span class="badge bg-primary">{{ "%.3f"|format(r.score) }}</span></td>
    <td><a href="/part/{{ r.part_number }}">{{ r.part_number }}</a></td>
    <td>{{ r.name }}</td>
    <td>{{ r.category }}</td>
    <td>{{ r.brand }}</td>
    <td>{% if r.price %}${{ "%.2f"|format(r.price) }}{% else %}—{% endif %}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% elif q and not error %}
<div class="alert alert-secondary">No results for "{{ q }}"</div>
{% endif %}
"""
    return render(tpl, page="search", q=q, cat=cat,
                  results=results, error=error, faiss_ok=faiss_ok)


# ── Data quality ──────────────────────────────────────────────────────────────

@app.route("/quality")
def data_quality():
    if not _parts:
        return render("<div class='alert alert-warning'>No parts loaded yet.</div>", page="quality")

    def pct(n): return round(n / len(_parts) * 100, 1) if _parts else 0

    fields = [
        ("Name",              sum(1 for p in _parts if p.get("name"))),
        ("Price",             sum(1 for p in _parts if p.get("price", 0) > 0)),
        ("Description",       sum(1 for p in _parts if p.get("description"))),
        ("Brand",             sum(1 for p in _parts if p.get("brand"))),
        ("Rating",            sum(1 for p in _parts if p.get("rating", 0) > 0)),
        ("Symptoms",          sum(1 for p in _parts if p.get("symptoms"))),
        ("Compatible Models", sum(1 for p in _parts if p.get("compatible_models"))),
        ("Install Difficulty",sum(1 for p in _parts if p.get("install_difficulty"))),
        ("Video URL",         sum(1 for p in _parts if p.get("video_url"))),
        ("Image URL",         sum(1 for p in _parts if p.get("image_url"))),
        ("MPN",               sum(1 for p in _parts if p.get("mpn"))),
        ("Availability",      sum(1 for p in _parts if p.get("availability"))),
    ]

    # Parts with no symptoms and no description (poor quality)
    poor = [p for p in _parts if not p.get("symptoms") and not p.get("description")]
    # Parts with no price
    no_price = [p for p in _parts if not p.get("price", 0)]
    # Parts with 0 compatible models
    no_models = [p for p in _parts if not p.get("compatible_models")]

    tpl = """
<div class="row g-4">
  <div class="col-md-6">
    <div class="card p-3">
      <h6 class="mb-3">Field Coverage ({{ total }} parts)</h6>
      {% for field, count in fields %}
      <div class="mb-2">
        <div class="d-flex justify-content-between small mb-1">
          <span>{{ field }}</span>
          <span>{{ count }} / {{ total }} &nbsp; ({{ "%.1f"|format(count/total*100 if total else 0) }}%)</span>
        </div>
        <div class="progress quality-bar">
          <div class="progress-bar {% if count/total > 0.8 %}bg-success{% elif count/total > 0.5 %}bg-warning{% else %}bg-danger{% endif %}"
               style="width:{{ "%.1f"|format(count/total*100 if total else 0) }}%"></div>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>

  <div class="col-md-6">
    <div class="card p-3 mb-3">
      <h6>Parts with no description AND no symptoms ({{ poor_n }})</h6>
      <small class="text-muted">These will have weak semantic search results.</small>
      {% if poor %}
      <div class="mt-2" style="max-height:150px;overflow-y:auto">
        {% for p in poor[:30] %}
        <a href="/part/{{ p.part_number }}" class="badge bg-light text-dark border me-1 mb-1">{{ p.part_number }}</a>
        {% endfor %}
        {% if poor|length > 30 %}<small class="text-muted"> + {{ poor|length - 30 }} more</small>{% endif %}
      </div>
      {% endif %}
    </div>

    <div class="card p-3 mb-3">
      <h6>Parts with no price ({{ no_price_n }})</h6>
      <div class="mt-2" style="max-height:100px;overflow-y:auto">
        {% for p in no_price[:20] %}
        <a href="/part/{{ p.part_number }}" class="badge bg-light text-dark border me-1 mb-1">{{ p.part_number }}</a>
        {% endfor %}
        {% if no_price|length > 20 %}<small class="text-muted"> + {{ no_price|length - 20 }} more</small>{% endif %}
      </div>
    </div>

    <div class="card p-3">
      <h6>Scrape source breakdown</h6>
      {% set direct_n  = parts | selectattr('_source', 'equalto', 'direct')  | list | length %}
      {% set wayback_n = parts | selectattr('_source', 'equalto', 'wayback') | list | length %}
      <div class="d-flex gap-3 mt-2">
        <div><span class="badge bg-success">{{ direct_n }}</span> direct</div>
        <div><span class="badge bg-warning text-dark">{{ wayback_n }}</span> wayback</div>
        <div><span class="badge bg-secondary">{{ total - direct_n - wayback_n }}</span> other</div>
      </div>
    </div>
  </div>
</div>
"""
    return render(tpl, page="quality",
                  total=len(_parts), fields=fields, parts=_parts,
                  poor=poor, poor_n=len(poor),
                  no_price=no_price, no_price_n=len(no_price),
                  no_models=no_models)


# ── Repairs browser ───────────────────────────────────────────────────────────

@app.route("/repairs")
def repairs_browser():
    cat = request.args.get("cat", "")
    sym = request.args.get("sym", "").strip().lower()

    filtered = _repairs
    if cat:
        filtered = [r for r in filtered if r.get("appliance") == cat]
    if sym:
        filtered = [r for r in filtered if sym in r.get("symptom", "").lower()]

    # Top symptoms by parts count
    top_symptoms = sorted(_symptom_map.items(), key=lambda x: -len(x[1]))[:15]

    tpl = """
<div class="row mb-3">
  <div class="col-md-6">
    <form method="get" class="d-flex gap-2">
      <input name="sym" value="{{ sym }}" class="form-control form-control-sm" placeholder="Filter by symptom...">
      <select name="cat" class="form-select form-select-sm" style="max-width:140px">
        <option value="">All</option>
        <option {% if cat=='refrigerator' %}selected{% endif %} value="refrigerator">Refrigerator</option>
        <option {% if cat=='dishwasher' %}selected{% endif %} value="dishwasher">Dishwasher</option>
      </select>
      <button class="btn btn-sm btn-primary">Filter</button>
      <a href="/repairs" class="btn btn-sm btn-outline-secondary">Clear</a>
    </form>
  </div>
  <div class="col text-muted small d-flex align-items-center">{{ filtered|length }} / {{ total }} repair guides</div>
</div>

<div class="row g-3">
<div class="col-md-8">
<div class="card">
<table class="table table-hover table-sm mb-0">
  <thead class="table-light">
    <tr><th>Appliance</th><th>Symptom</th><th>Parts Linked</th><th>URL</th></tr>
  </thead>
  <tbody>
  {% for r in repairs %}
  <tr>
    <td>
      {% if r.appliance=='refrigerator' %}
        <span class="badge badge-fridge">fridge</span>
      {% else %}
        <span class="badge badge-dish">dish</span>
      {% endif %}
    </td>
    <td>{{ r.symptom }}</td>
    <td>
      {% set key = r.appliance + '|' + r.symptom %}
      {% set pts = symptom_map.get(key, []) %}
      {% if pts %}
        <span class="badge bg-success">{{ pts|length }}</span>
      {% else %}
        <span class="text-muted">—</span>
      {% endif %}
    </td>
    <td><a href="{{ r.url }}" target="_blank" class="text-muted small">link</a></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
</div>

<div class="col-md-4">
  <div class="card p-3">
    <h6>Top Symptoms by Parts</h6>
    {% for key, parts in top_symptoms %}
    <div class="d-flex justify-content-between align-items-center mb-1 small">
      <span style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ key }}</span>
      <span class="badge bg-primary">{{ parts|length }}</span>
    </div>
    {% endfor %}
  </div>
</div>
</div>
"""
    return render(tpl, page="repairs",
                  repairs=filtered, total=len(_repairs),
                  cat=cat, sym=sym,
                  symptom_map=_symptom_map,
                  top_symptoms=top_symptoms)


# ── Blogs browser ─────────────────────────────────────────────────────────────

@app.route("/blogs")
def blogs_browser():
    cat = request.args.get("cat", "")
    q   = request.args.get("q", "").strip().lower()

    filtered = _blogs
    if cat:
        filtered = [b for b in filtered if b.get("appliance") == cat]
    if q:
        filtered = [b for b in filtered
                    if q in b.get("title","").lower() or q in b.get("summary","").lower()]

    tpl = """
<div class="row mb-3">
  <div class="col-md-7">
    <form method="get" class="d-flex gap-2">
      <input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Search blogs...">
      <select name="cat" class="form-select form-select-sm" style="max-width:140px">
        <option value="">All</option>
        <option {% if cat=='refrigerator' %}selected{% endif %} value="refrigerator">Refrigerator</option>
        <option {% if cat=='dishwasher' %}selected{% endif %} value="dishwasher">Dishwasher</option>
        <option {% if cat=='both' %}selected{% endif %} value="both">Both</option>
        <option {% if cat=='general' %}selected{% endif %} value="general">General</option>
      </select>
      <button class="btn btn-sm btn-primary">Filter</button>
      <a href="/blogs" class="btn btn-sm btn-outline-secondary">Clear</a>
    </form>
  </div>
  <div class="col text-muted small d-flex align-items-center">{{ filtered|length }} / {{ total }} articles</div>
</div>

<div class="card">
<table class="table table-hover table-sm mb-0">
  <thead class="table-light">
    <tr><th>Title</th><th>Appliance</th><th>Parts</th><th>Keywords</th><th>Link</th></tr>
  </thead>
  <tbody>
  {% for b in filtered %}
  <tr>
    <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ b.title }}">{{ b.title }}</td>
    <td>
      {% if b.appliance=='refrigerator' %}<span class="badge badge-fridge">fridge</span>
      {% elif b.appliance=='dishwasher' %}<span class="badge badge-dish">dish</span>
      {% elif b.appliance=='both' %}<span class="badge bg-purple" style="background:#6f42c1">both</span>
      {% else %}<span class="badge bg-secondary">general</span>{% endif %}
    </td>
    <td>
      {% if b.parts_mentioned %}
        <span class="badge bg-success">{{ b.parts_mentioned|length }}</span>
      {% else %}—{% endif %}
    </td>
    <td style="max-width:180px;font-size:.8rem">{{ (b.symptom_keywords or [])[:4]|join(", ") }}</td>
    <td><a href="{{ b.url }}" target="_blank" class="text-muted small">link</a></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
"""
    return render(tpl, page="blogs",
                  blogs=filtered[:200], total=len(_blogs),
                  cat=cat, q=q, filtered=filtered)


# ── Relations view ────────────────────────────────────────────────────────────

@app.route("/relations")
def relations_view():
    top_types = sorted(_part_type_map.items(),
                       key=lambda x: -x[1].get("count", 0))[:20]
    top_symptoms = sorted(_symptom_map.items(), key=lambda x: -len(x[1]))[:20]
    rs = _rel_summary

    tpl = """
<div class="row g-3 mb-4">
  {% set stats = [
    ("Scraped Parts", rs.get('scraped_parts',0), "#1b3875"),
    ("Sitemap Parts", rs.get('sitemap_parts',0), "#6610f2"),
    ("Symptom Keys", rs.get('symptom_keys',0), "#dc3545"),
    ("Part Type Keys", rs.get('part_type_keys',0), "#fd7e14"),
    ("Model Mappings", rs.get('model_keys',0), "#198754"),
    ("Brand x Appliance", rs.get('brand_appliance_keys',0), "#0dcaf0"),
    ("Repair Guides", rs.get('repair_guides',0), "#6c757d"),
    ("Blog Articles", rs.get('blogs',0), "#6c757d"),
  ] %}
  {% for label, val, color in stats %}
  <div class="col-md-3">
    <div class="card stat-card p-3" style="border-color:{{ color }}">
      <div class="text-muted small">{{ label }}</div>
      <div class="stat-num" style="color:{{ color }}">{{ val }}</div>
    </div>
  </div>
  {% endfor %}
</div>

<div class="row g-3">
  <div class="col-md-6">
    <div class="card p-3">
      <h6 class="mb-3">Top Part Types by Part Count</h6>
      {% for key, val in top_types %}
      <div class="d-flex justify-content-between align-items-center mb-1 small">
        <span>{{ key }}</span>
        <div>
          <span class="badge bg-primary me-1">{{ val.count }}</span>
          <span class="badge bg-secondary">{{ val.brands|length }} brands</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>

  <div class="col-md-6">
    <div class="card p-3">
      <h6 class="mb-3">Top Symptoms by Part Count</h6>
      {% for key, parts in top_symptoms %}
      <div class="d-flex justify-content-between align-items-center mb-1 small">
        <span style="max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ key }}</span>
        <span class="badge bg-danger">{{ parts|length }}</span>
      </div>
      {% endfor %}
    </div>
  </div>
</div>

<div class="row g-3 mt-1">
  <div class="col-md-12">
    <div class="card p-3">
      <h6>Top Brands by Sitemap Coverage</h6>
      <div class="d-flex flex-wrap gap-2 mt-2">
        {% for item in rs.get('top_brands',[]) %}
        <span class="badge bg-light text-dark border" style="font-size:.9rem">
          {{ item.brand }} <span class="text-primary">{{ item.count }}</span>
        </span>
        {% endfor %}
      </div>
    </div>
  </div>
</div>
"""
    return render(tpl, page="relations",
                  top_types=top_types, top_symptoms=top_symptoms, rs=rs)


# ── Reload + API ──────────────────────────────────────────────────────────────

@app.route("/reload")
def reload_endpoint():
    reload_data()
    return redirect(url_for("dashboard"))


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "parts_total":      len(_parts),
        "refrigerator":     sum(1 for p in _parts if p.get("category") == "refrigerator"),
        "dishwasher":       sum(1 for p in _parts if p.get("category") == "dishwasher"),
        "models_mapped":    len(_model_map),
        "with_price":       sum(1 for p in _parts if p.get("price", 0) > 0),
        "with_symptoms":    sum(1 for p in _parts if p.get("symptoms")),
        "with_models":      sum(1 for p in _parts if p.get("compatible_models")),
        "sitemap_total":    len(_sitemap),
        "repair_guides":    len(_repairs),
        "blogs":            len(_blogs),
        "symptom_keys":     len(_symptom_map),
        "part_type_keys":   len(_part_type_map),
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    load_data()
    print(f"Loaded {len(_parts)} parts, {len(_model_map)} model mappings")
    print("Inspector running at http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)
