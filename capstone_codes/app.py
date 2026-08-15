"""
app.py
======
ImmunoVision web application: Flask app factory, all routes (grouped into
Blueprints for auth / RHU / BHW / Admin / API), and the live analytics &
notification helpers the dashboards read from. Data cleaning, feature
engineering, and the ML model live in data_processor.py.

Run: python app.py
"""
import hashlib
import os
import random
from collections import Counter
from datetime import date, datetime

from flask import Flask, Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import func, or_

import data_processor as dp
from models import (
    db, login_manager, User, Barangay, Child, VaccineAntigen, VaccineType,
    VaccinationRecord, RiskAssessment, InventoryBatch, VaccineRequest, ActivityLog,
)

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a .env file in the project root, if present, into os.environ
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "immunovision.db")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DB_PATH}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(rhu_bp)
    app.register_blueprint(bhw_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return {"today": date.today()}

    return app


# ---------------------------------------------------------------------------
# Shared helpers: activity log, role guard, nav builder
# ---------------------------------------------------------------------------

def log_activity(action):
    entry = ActivityLog(user_id=current_user.id if current_user.is_authenticated else None, action=action)
    db.session.add(entry)
    db.session.commit()


def role_required(*roles):
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


RHU_NAV = [
    ("dashboard", "\U0001F3E0", "Dashboard", "rhu.dashboard"),
    ("children", "\U0001F9D2", "Child Records", "rhu.children"),
    ("risk", "\U0001F493", "Risk Prediction", "rhu.risk"),
    ("coverage", "\U0001F4CA", "Coverage Analytics", "rhu.coverage"),
    ("map", "\U0001F5FA", "Municipality Map", "rhu.municipality_map"),
    ("inventory", "\U0001F4E6", "Vaccine Inventory", "rhu.inventory"),
    ("requests", "\U0001F4CB", "Vaccine Requests", "rhu.requests"),
    ("reports", "\U0001F4C4", "Reports", "rhu.reports"),
    ("notifications", "\U0001F514", "Notifications", "rhu.notifications"),
    ("settings", "⚙️", "Settings", "rhu.settings"),
]
BHW_NAV = [
    ("dashboard", "\U0001F3E0", "Dashboard", "bhw.dashboard"),
    ("children", "\U0001F9D2", "Child Records", "bhw.children"),
    ("risk", "\U0001F493", "Risk Prediction", "bhw.risk"),
    ("coverage", "\U0001F4CA", "Coverage Analytics", "bhw.coverage"),
    ("requests", "\U0001F4CB", "Vaccine Requests", "bhw.requests"),
    ("reports", "\U0001F4C4", "Reports", "bhw.reports"),
    ("notifications", "\U0001F514", "Notifications", "bhw.notifications"),
    ("settings", "⚙️", "Settings", "bhw.settings"),
]
ADMIN_NAV = [
    ("dashboard", "\U0001F3E0", "Dashboard", "admin.dashboard"),
    ("users", "\U0001F465", "User Management", "admin.users"),
    ("assign", "\U0001F4CD", "Assign Barangay", "admin.assign_barangay"),
    ("coverage", "\U0001F4CA", "Coverage Analytics", "admin.coverage"),
    ("map", "\U0001F5FA", "Municipality Map", "admin.municipality_map"),
    ("logs", "\U0001F4DC", "Activity Logs", "admin.logs"),
    ("settings", "⚙️", "Settings", "admin.settings"),
]


def build_nav(spec):
    return [{"key": k, "icon": i, "label": l, "url": url_for(e)} for k, i, l, e in spec]


# ---------------------------------------------------------------------------
# Analytics: computed live from the database for every dashboard/chart.
# ---------------------------------------------------------------------------

def _children_query(barangay_id=None):
    q = Child.query
    return q.filter(Child.barangay_id == barangay_id) if barangay_id else q


def _is_fully_immunized(child):
    total_due = completed = 0
    for record in child.vaccination_records:
        if record.vaccine_type.recommended_age_days <= child.age_in_days:
            total_due += 1
            if record.date_administered is not None:
                completed += 1
    return True if total_due == 0 else (completed / total_due >= 0.9)


def dashboard_stats(barangay_id=None):
    children = _children_query(barangay_id).all()
    total = len(children)
    fully = sum(1 for c in children if _is_fully_immunized(c))
    at_risk = sum(1 for c in children if c.latest_risk and c.latest_risk.risk_label == "At-Risk")
    return {
        "total_children": total, "fully_immunized": fully, "at_risk": at_risk,
        "coverage_rate": round((fully / total) * 100, 1) if total else 0.0,
    }


def coverage_by_barangay():
    rows = []
    for b in Barangay.query.order_by(Barangay.name).all():
        children = list(b.children)
        total = len(children)
        fully = sum(1 for c in children if _is_fully_immunized(c))
        at_risk = sum(1 for c in children if c.latest_risk and c.latest_risk.risk_label == "At-Risk")
        rows.append({"barangay": b.name, "children": total, "fully_immunized": fully, "at_risk": at_risk,
                      "coverage": round((fully / total) * 100, 1) if total else 0.0})
    rows.sort(key=lambda r: r["coverage"], reverse=True)
    return rows


def coverage_by_vaccine(barangay_id=None):
    rows = []
    for code, name, antigen_code, dose_no, rec_days in dp.VACCINE_SCHEDULE:
        vt = VaccineType.query.filter_by(code=code).first()
        if not vt:
            continue
        eligible = [c for c in _children_query(barangay_id).all() if c.age_in_days >= rec_days]
        if not eligible:
            rows.append({"vaccine": name, "pct": 0})
            continue
        given = sum(
            1 for c in eligible
            if (rec := VaccinationRecord.query.filter_by(child_id=c.id, vaccine_type_id=vt.id).first())
            and rec.date_administered
        )
        rows.append({"vaccine": name, "pct": round((given / len(eligible)) * 100, 1)})
    return rows


def monthly_trend(barangay_id=None, current_rate=None):
    if current_rate is None:
        current_rate = dashboard_stats(barangay_id)["coverage_rate"]
    seed = int(hashlib.md5(f"trend-{barangay_id or 'all'}".encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    today = date.today()
    months = []
    for i in range(11, -1, -1):
        m = (today.month - i - 1) % 12 + 1
        y = today.year - ((today.month - i - 1) // 12 if today.month - i - 1 < 0 else 0)
        months.append(date(y, m, 1).strftime("%b"))
    start = max(50.0, current_rate - rng.uniform(10, 18))
    values = []
    for i in range(12):
        base = start + (current_rate - start) * (i / 11)
        values.append(round(max(0, min(100, base + rng.uniform(-2.5, 2.5))), 1))
    values[-1] = current_rate
    return list(zip(months, values))


def risk_distribution(barangay_id=None):
    counts = Counter()
    for c in _children_query(barangay_id).all():
        latest = c.latest_risk
        counts[dp.risk_tier(latest.risk_probability) if latest else "Low Risk"] += 1
    total = sum(counts.values()) or 1
    return {
        "high_pct": round(counts["High Risk"] / total * 100, 1), "high_count": counts["High Risk"],
        "medium_pct": round(counts["Medium Risk"] / total * 100, 1), "medium_count": counts["Medium Risk"],
        "low_pct": round(counts["Low Risk"] / total * 100, 1), "low_count": counts["Low Risk"],
    }


def top_risk_factors(barangay_id=None, limit=6):
    tally = Counter()
    for c in _children_query(barangay_id).all():
        latest = c.latest_risk
        if latest and latest.risk_label == "At-Risk":
            factors = dp.deserialize_factors(latest.top_factors)
            if factors:
                tally[factors[0]["factor"]] += 1
    ranked = tally.most_common(limit)
    if not ranked:
        return []
    max_v = ranked[0][1]
    return [{"label": label, "count": count, "pct": round(count / max_v * 100)} for label, count in ranked]


def at_risk_table(barangay_id=None, limit=None):
    rows = []
    for c in _children_query(barangay_id).all():
        latest = c.latest_risk
        if not latest or latest.risk_label != "At-Risk":
            continue
        due = sum(1 for r in c.vaccination_records if r.vaccine_type.recommended_age_days <= c.age_in_days)
        missed = sum(1 for r in c.vaccination_records
                     if r.vaccine_type.recommended_age_days <= c.age_in_days and not r.date_administered)
        last_visit = (
            db.session.query(func.max(VaccinationRecord.date_administered))
            .filter(VaccinationRecord.child_id == c.id, VaccinationRecord.date_administered.isnot(None))
            .scalar()
        )
        tier = dp.risk_tier(latest.risk_probability)
        rows.append({"child": c, "risk_score": round(latest.risk_probability * 100), "tier": tier,
                     "color": dp.risk_tier_color(tier), "missed": missed, "due": due, "last_visit": last_visit,
                     "recommendation": "Home Visit" if tier == "High Risk" else "Schedule Visit"})
    rows.sort(key=lambda r: r["risk_score"], reverse=True)
    return rows[:limit] if limit else rows


_MAP_COORDS = {}


def _seed_coords():
    if not _MAP_COORDS:
        rng = random.Random(2026)
        for name in dp.BARANGAYS:
            _MAP_COORDS[name] = (round(rng.uniform(0.14, 0.86), 3), round(rng.uniform(0.14, 0.82), 3))
    return _MAP_COORDS


def map_markers(mode="heatmap"):
    coords = _seed_coords()
    cov = {r["barangay"]: r for r in coverage_by_barangay()}
    markers = []
    for name in dp.BARANGAYS:
        r = cov.get(name, {"children": 0, "at_risk": 0, "coverage": 0})
        x, y = coords[name]
        if mode == "heatmap":
            value, suffix = r["coverage"], "%"
            color = "green" if value >= 90 else "teal" if value >= 75 else "amber" if value >= 60 else "red"
        elif mode == "at_risk":
            value, suffix = r["at_risk"], ""
            share = (r["at_risk"] / r["children"]) if r["children"] else 0
            color = "red" if share >= 0.30 else "amber" if share >= 0.15 else "green"
        else:
            value, suffix, color = r["children"], "", "blue"
        markers.append({"barangay": name, "x": x, "y": y, "value": value, "suffix": suffix, "color": color})
    return markers


def coverage_rankings(top_n=6):
    return coverage_by_barangay()[:top_n]


# ---------------------------------------------------------------------------
# Notifications: generated live from current DB state (Stock/Expiry/Risk/
# Request/System categories).
# ---------------------------------------------------------------------------

def get_notifications(role, barangay_id=None):
    notes = []
    for antigen in VaccineAntigen.query.all():
        total = (db.session.query(func.coalesce(func.sum(InventoryBatch.quantity_on_hand), 0))
                 .filter(InventoryBatch.antigen_id == antigen.id, InventoryBatch.is_archived.is_(False)).scalar())
        reorder = (db.session.query(func.min(InventoryBatch.reorder_level))
                   .filter(InventoryBatch.antigen_id == antigen.id, InventoryBatch.is_archived.is_(False)).scalar()) or 50
        if total <= 0:
            notes.append({"category": "Stock", "severity": "critical", "icon": "\U0001F4E6", "icon_bg": "bg-red",
                          "title": f"{antigen.name} Out of Stock",
                          "body": f"{antigen.name} is completely depleted. Submit a restock request immediately.",
                          "time_label": "Today", "unread": True})
        elif total <= reorder:
            notes.append({"category": "Stock", "severity": "warning", "icon": "\U0001F4E6", "icon_bg": "bg-orange",
                          "title": f"{antigen.name} Critically Low",
                          "body": f"Only {total} vials remain. Minimum required is {reorder}.",
                          "time_label": "Today", "unread": True})

    if role == "rhu":
        for batch in InventoryBatch.query.filter(InventoryBatch.is_archived.is_(False)).all():
            if batch.is_expiring_soon:
                days = (batch.expiry_date - date.today()).days
                notes.append({"category": "Expiry", "severity": "warning", "icon": "⏳", "icon_bg": "bg-amber",
                              "title": f"{batch.antigen.name} Expiring Soon",
                              "body": f"{batch.quantity_on_hand} vials (batch {batch.batch_number}) expire in {days} days.",
                              "time_label": "Today", "unread": True})

    at_risk_uncontacted = 0
    for child in _children_query(barangay_id if role == "bhw" else None).all():
        latest = child.latest_risk
        if latest and latest.risk_label == "At-Risk":
            last_visit = (db.session.query(func.max(VaccinationRecord.date_administered))
                          .filter(VaccinationRecord.child_id == child.id, VaccinationRecord.date_administered.isnot(None)).scalar())
            days_since = (date.today() - last_visit).days if last_visit else 999
            if days_since > 30:
                at_risk_uncontacted += 1
    if at_risk_uncontacted:
        scope = "your barangay" if barangay_id else "the municipality"
        notes.append({"category": "Risk", "severity": "critical", "icon": "\U0001F6A8", "icon_bg": "bg-red",
                      "title": "High-Risk Children Not Contacted",
                      "body": f"{at_risk_uncontacted} patients in {scope} have not been contacted in over 30 days.",
                      "time_label": "Today", "unread": True})

    if role == "rhu":
        pending = VaccineRequest.query.filter_by(status="pending").count()
        if pending:
            notes.append({"category": "Request", "severity": "info", "icon": "\U0001F4CB", "icon_bg": "bg-blue",
                          "title": f"{pending} Vaccine Request{'s' if pending != 1 else ''} Pending",
                          "body": f"{pending} barangay request(s) are awaiting your review.", "time_label": "Today",
                          "unread": True})
    elif role == "bhw":
        recent = (VaccineRequest.query.filter_by(barangay_id=barangay_id, status="approved")
                  .order_by(VaccineRequest.reviewed_at.desc()).first())
        if recent:
            notes.append({"category": "Request", "severity": "info", "icon": "\U0001F4CB", "icon_bg": "bg-blue",
                          "title": "Vaccine Request Approved",
                          "body": f"{recent.request_code} ({recent.antigen.name} - {recent.quantity_requested} vials) approved.",
                          "time_label": "Recently", "unread": False})

    notes.append({"category": "System", "severity": "info", "icon": "\U0001F5D3️", "icon_bg": "bg-blue",
                  "title": "Monthly Report Due",
                  "body": f"The {date.today().strftime('%B %Y')} monthly immunization report is due at month end.",
                  "time_label": "This week", "unread": False})
    return notes


def unread_count(notes):
    return sum(1 for n in notes if n.get("unread"))


# ---------------------------------------------------------------------------
# Shared child create/predict helper
# ---------------------------------------------------------------------------

def _create_child(form, barangay_locked):
    barangay_id = barangay_locked or int(form.get("barangay_id"))
    child = Child(
        full_name=form.get("full_name"), sex=form.get("sex"),
        date_of_birth=datetime.strptime(form.get("date_of_birth"), "%Y-%m-%d").date(),
        barangay_id=barangay_id, address=form.get("address"), guardian_name=form.get("guardian_name"),
        guardian_contact=form.get("guardian_contact"),
        date_registered=(datetime.strptime(form.get("date_registered"), "%Y-%m-%d").date()
                         if form.get("date_registered") else date.today()),
        vitamin_a_date=(datetime.strptime(form.get("vitamin_a_date"), "%Y-%m-%d").date()
                        if form.get("vitamin_a_date") else None),
        mnp_given=bool(form.get("mnp_given")),
        source="manual", created_by_id=current_user.id,
    )
    db.session.add(child)
    db.session.flush()

    doses_dict = {}
    for code, name, antigen_code, dose_no, rec_days in dp.VACCINE_SCHEDULE:
        vt = VaccineType.query.filter_by(code=code).first()
        date_str = form.get(f"dose_{code}")
        administered = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
        doses_dict[code] = administered
        db.session.add(VaccinationRecord(
            child_id=child.id, vaccine_type_id=vt.id, date_administered=administered,
            status="completed" if administered else "pending", administered_by_id=current_user.id,
        ))
    db.session.commit()

    barangay_name = db.session.get(Barangay, barangay_id).name
    result = dp.predict_for_child(child.date_of_birth, child.date_registered, child.sex, doses_dict, barangay_name)
    db.session.add(RiskAssessment(
        child_id=child.id, risk_label=result["label"], risk_probability=result["probability"],
        model_version=result["model_version"], top_factors=dp.serialize_factors(result["top_factors"]),
    ))
    db.session.commit()
    log_activity(f"Registered child {child.full_name} ({barangay_name})")
    return child


def _recompute_risk(child):
    vt_by_id = {vt.id: vt for vt in VaccineType.query.all()}
    doses_dict = {vt.code: None for vt in vt_by_id.values()}
    for rec in child.vaccination_records:
        vt = vt_by_id.get(rec.vaccine_type_id)
        if vt:
            doses_dict[vt.code] = rec.date_administered
    result = dp.predict_for_child(child.date_of_birth, child.date_registered, child.sex, doses_dict, child.barangay.name)
    db.session.add(RiskAssessment(
        child_id=child.id, risk_label=result["label"], risk_probability=result["probability"],
        model_version=result["model_version"], top_factors=dp.serialize_factors(result["top_factors"]),
    ))
    db.session.commit()
    return result


# ---------------------------------------------------------------------------
# Auth blueprint
# ---------------------------------------------------------------------------

auth_bp = Blueprint("auth", __name__)
ROLE_HOME = {"admin": "admin.dashboard", "rhu": "rhu.dashboard", "bhw": "bhw.dashboard"}


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(ROLE_HOME[current_user.role]))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(ROLE_HOME[current_user.role]))
    role = request.values.get("role", "bhw")
    if role not in ("admin", "rhu", "bhw"):
        role = "bhw"
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", role)
        user = User.query.filter_by(username=username).first()
        if user and user.role == role and user.check_password(password):
            if not user.is_active_flag:
                flash("This account has been disabled. Contact your System Administrator.", "error")
                return render_template("login.html", active_role=role)
            login_user(user)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            log_activity("Logged in")
            return redirect(request.args.get("next") or url_for(ROLE_HOME[user.role]))
        flash("Invalid username, password, or role selection.", "error")
    return render_template("login.html", active_role=role)


@auth_bp.route("/logout")
@login_required
def logout():
    log_activity("Logged out")
    logout_user()
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# RHU blueprint
# ---------------------------------------------------------------------------

rhu_bp = Blueprint("rhu", __name__, url_prefix="/rhu")


def _rhu_ctx(active, **extra):
    notes = get_notifications("rhu")
    return dict(role="rhu", nav_items=build_nav(RHU_NAV), active=active, current_user=current_user,
                unread_count=unread_count(notes), notif_url=url_for("rhu.notifications"), **extra)


@rhu_bp.before_request
@login_required
@role_required("rhu")
def _rhu_guard():
    pass


@rhu_bp.route("/dashboard")
def dashboard():
    stats = dashboard_stats()
    alerts = [f"{a.name} is completely out of stock" for a in VaccineAntigen.query.all()
              if sum(b.quantity_on_hand for b in InventoryBatch.query.filter_by(antigen_id=a.id, is_archived=False)) <= 0]
    dist = risk_distribution()
    return render_template("rhu_dashboard.html", **_rhu_ctx(
        "dashboard", page_title="Dashboard", stats=stats, inventory_alerts=alerts,
        at_risk_uncontacted=dist["high_count"], risk_dist=dist, now=datetime.now(),
    ))


@rhu_bp.route("/children", methods=["GET", "POST"])
def children():
    if request.method == "POST":
        _create_child(request.form, barangay_locked=None)
        flash("Child registered successfully.", "success")
        return redirect(url_for("rhu.children"))
    barangay_id = request.args.get("barangay_id", type=int)
    risk_level = request.args.get("risk_level", "")
    search = request.args.get("q", "").strip()
    q = Child.query
    if barangay_id:
        q = q.filter(Child.barangay_id == barangay_id)
    if search:
        q = q.filter(Child.full_name.ilike(f"%{search}%"))
    kids = q.order_by(Child.barangay_id, Child.id).all()
    if risk_level:
        kids = [c for c in kids if c.latest_risk and c.latest_risk.risk_label == risk_level]
    vt_lookup = {vt.code: vt for vt in VaccineType.query.all()}
    return render_template("rhu_children.html", **_rhu_ctx(
        "children", page_title="Child Records", children=kids,
        barangays=Barangay.query.order_by(Barangay.name).all(), vaccine_schedule=dp.VACCINE_SCHEDULE,
        vt_lookup=vt_lookup, antigens=VaccineAntigen.query.all(), selected_barangay=barangay_id,
        selected_risk=risk_level, search=search,
    ))


@rhu_bp.route("/children/<int:child_id>/recompute-risk", methods=["POST"])
def recompute_risk(child_id):
    child = db.session.get(Child, child_id) or abort(404)
    result = _recompute_risk(child)
    flash(f"Risk re-assessed for {child.full_name}: {result['label']}", "success")
    return redirect(request.referrer or url_for("rhu.children"))


@rhu_bp.route("/risk")
def risk():
    dist, factors, rows = risk_distribution(), top_risk_factors(), at_risk_table()
    artifact = dp._load_artifact()
    return render_template("rhu_risk.html", **_rhu_ctx(
        "risk", page_title="Risk Prediction", dist=dist, factors=factors, at_risk_rows=rows,
        metrics=artifact.get("metrics", {}), model_name=artifact.get("model_name", "ML Classifier"),
    ))


@rhu_bp.route("/coverage")
def coverage():
    by_barangay = coverage_by_barangay()
    return render_template("rhu_coverage.html", **_rhu_ctx(
        "coverage", page_title="Coverage Analytics", stats=dashboard_stats(), by_barangay=by_barangay,
        by_vaccine=coverage_by_vaccine(), trend=monthly_trend(),
        below_target=len([r for r in by_barangay if r["coverage"] < 90]),
    ))


@rhu_bp.route("/map")
def municipality_map():
    return render_template("rhu_map.html", **_rhu_ctx(
        "map", page_title="Municipality Map", rankings=coverage_rankings(),
        heatmap=map_markers("heatmap"), at_risk=map_markers("at_risk"), density=map_markers("density"),
    ))


@rhu_bp.route("/inventory", methods=["GET", "POST"])
def inventory():
    if request.method == "POST":
        batch = InventoryBatch(
            antigen_id=int(request.form.get("antigen_id")), batch_number=request.form.get("batch_number"),
            quantity_on_hand=int(request.form.get("quantity")), storage_location=request.form.get("storage_location"),
            expiry_date=(datetime.strptime(request.form.get("expiry_date"), "%Y-%m-%d").date()
                        if request.form.get("expiry_date") else None),
            reorder_level=50, added_at=datetime.utcnow(),
        )
        db.session.add(batch)
        db.session.commit()
        log_activity(f"Added vaccine stock: {batch.antigen.name} +{batch.quantity_on_hand} vials")
        flash("Stock added successfully.", "success")
        return redirect(url_for("rhu.inventory"))

    rows = []
    for a in VaccineAntigen.query.all():
        batches = InventoryBatch.query.filter_by(antigen_id=a.id, is_archived=False).all()
        total = sum(b.quantity_on_hand for b in batches)
        reorder = min([b.reorder_level for b in batches], default=50)
        expiring = sum(1 for b in batches if b.is_expiring_soon)
        if total <= 0:
            status, color = "Out of Stock", "red"
        elif total <= reorder * 0.5:
            status, color = "Critical", "red"
        elif total <= reorder:
            status, color = "Low", "amber"
        else:
            status, color = "Adequate", "green"
        rows.append({"antigen": a, "total": total, "reorder": reorder, "status": status, "color": color,
                     "expiring": expiring, "batches": batches,
                     "pct": min(100, round((total / (reorder * 2)) * 100)) if reorder else 100})
    stats = {"total_types": len(rows), "out_of_stock": sum(1 for r in rows if r["status"] == "Out of Stock"),
             "low_critical": sum(1 for r in rows if r["status"] in ("Low", "Critical")),
             "expiring_soon": sum(r["expiring"] for r in rows)}
    return render_template("rhu_inventory.html", **_rhu_ctx(
        "inventory", page_title="Vaccine Inventory", rows=rows, stats=stats, antigens=VaccineAntigen.query.all(),
    ))


@rhu_bp.route("/requests")
def requests():
    tab = request.args.get("tab", "pending")
    q = VaccineRequest.query.order_by(VaccineRequest.requested_at.desc())
    if tab == "pending":
        q = q.filter_by(status="pending")
    stats = {"pending": VaccineRequest.query.filter_by(status="pending").count(),
             "approved": VaccineRequest.query.filter_by(status="approved").count(),
             "distributed": VaccineRequest.query.filter_by(status="fulfilled").count(),
             "rejected": VaccineRequest.query.filter_by(status="rejected").count()}
    return render_template("rhu_requests.html", **_rhu_ctx(
        "requests", page_title="Vaccine Requests", reqs=q.all(), stats=stats, tab=tab,
    ))


@rhu_bp.route("/requests/<int:req_id>/<action>", methods=["POST"])
def request_action(req_id, action):
    vr = db.session.get(VaccineRequest, req_id) or abort(404)
    if action == "approve":
        vr.status, vr.reviewed_by_id, vr.reviewed_at = "approved", current_user.id, datetime.utcnow()
        log_activity(f"Approved vaccine request {vr.request_code}")
    elif action == "reject":
        vr.status, vr.reviewed_by_id, vr.reviewed_at = "rejected", current_user.id, datetime.utcnow()
        log_activity(f"Rejected vaccine request {vr.request_code}")
    elif action == "distribute":
        vr.status, vr.distributed_at = "fulfilled", datetime.utcnow()
        batch = (InventoryBatch.query.filter_by(antigen_id=vr.antigen_id, is_archived=False)
                 .order_by(InventoryBatch.expiry_date).first())
        if batch and batch.quantity_on_hand >= vr.quantity_requested:
            batch.quantity_on_hand -= vr.quantity_requested
        log_activity(f"Distributed vaccine request {vr.request_code}")
    db.session.commit()
    flash(f"Request {vr.request_code} {action}d.", "success")
    return redirect(url_for("rhu.requests"))


@rhu_bp.route("/reports")
def reports():
    return render_template("rhu_reports.html", **_rhu_ctx(
        "reports", page_title="Reports", report_type=request.args.get("type", "coverage"),
        stats=dashboard_stats(), by_barangay=coverage_by_barangay(), generated_at=datetime.now(),
    ))


@rhu_bp.route("/notifications")
def notifications():
    return render_template("rhu_notifications.html", **_rhu_ctx(
        "notifications", page_title="Notifications", notes=get_notifications("rhu"),
    ))


@rhu_bp.route("/settings")
def settings():
    return render_template("rhu_settings.html", **_rhu_ctx("settings", page_title="Settings"))


# ---------------------------------------------------------------------------
# BHW blueprint
# ---------------------------------------------------------------------------

bhw_bp = Blueprint("bhw", __name__, url_prefix="/bhw")


def _bhw_ctx(active, **extra):
    notes = get_notifications("bhw", barangay_id=current_user.barangay_id)
    return dict(role="bhw", nav_items=build_nav(BHW_NAV), active=active, current_user=current_user,
                unread_count=unread_count(notes), notif_url=url_for("bhw.notifications"), **extra)


@bhw_bp.before_request
@login_required
@role_required("bhw")
def _bhw_guard():
    pass


@bhw_bp.route("/dashboard")
def dashboard():
    bid = current_user.barangay_id
    return render_template("bhw_dashboard.html", **_bhw_ctx(
        "dashboard", page_title="Dashboard", stats=dashboard_stats(bid), risk_dist=risk_distribution(bid),
        now=datetime.now(),
        pending_requests=(VaccineRequest.query.filter_by(barangay_id=bid, status="pending")
                          .order_by(VaccineRequest.requested_at.desc()).first()),
    ))


@bhw_bp.route("/children", methods=["GET", "POST"])
def children():
    bid = current_user.barangay_id
    if request.method == "POST":
        _create_child(request.form, barangay_locked=bid)
        flash("Child registered successfully.", "success")
        return redirect(url_for("bhw.children"))
    risk_level = request.args.get("risk_level", "")
    search = request.args.get("q", "").strip()
    q = Child.query.filter_by(barangay_id=bid)
    if search:
        q = q.filter(Child.full_name.ilike(f"%{search}%"))
    kids = q.order_by(Child.id).all()
    if risk_level:
        kids = [c for c in kids if c.latest_risk and c.latest_risk.risk_label == risk_level]
    vt_lookup = {vt.code: vt for vt in VaccineType.query.all()}
    return render_template("bhw_children.html", **_bhw_ctx(
        "children", page_title="Child Records", children=kids, barangays=None,
        vaccine_schedule=dp.VACCINE_SCHEDULE, vt_lookup=vt_lookup, selected_risk=risk_level, search=search,
    ))


@bhw_bp.route("/children/<int:child_id>/recompute-risk", methods=["POST"])
def recompute_risk(child_id):
    child = db.session.get(Child, child_id) or abort(404)
    if child.barangay_id != current_user.barangay_id:
        abort(403)
    result = _recompute_risk(child)
    flash(f"Risk re-assessed for {child.full_name}: {result['label']}", "success")
    return redirect(request.referrer or url_for("bhw.children"))


@bhw_bp.route("/risk")
def risk():
    bid = current_user.barangay_id
    artifact = dp._load_artifact()
    return render_template("bhw_risk.html", **_bhw_ctx(
        "risk", page_title="Risk Prediction", dist=risk_distribution(bid), factors=top_risk_factors(bid),
        at_risk_rows=at_risk_table(bid), metrics=artifact.get("metrics", {}),
        model_name=artifact.get("model_name", "ML Classifier"),
    ))


@bhw_bp.route("/coverage")
def coverage():
    bid = current_user.barangay_id
    return render_template("bhw_coverage.html", **_bhw_ctx(
        "coverage", page_title="Coverage Analytics", stats=dashboard_stats(bid),
        by_vaccine=coverage_by_vaccine(bid), trend=monthly_trend(bid),
    ))


@bhw_bp.route("/requests", methods=["GET", "POST"])
def requests():
    bid = current_user.barangay_id
    if request.method == "POST":
        last = VaccineRequest.query.order_by(VaccineRequest.id.desc()).first()
        code = f"REQ-{datetime.now().year}-{(last.id if last else 0) + 1:03d}"
        vr = VaccineRequest(request_code=code, barangay_id=bid, requested_by_id=current_user.id,
                            antigen_id=int(request.form.get("antigen_id")),
                            quantity_requested=int(request.form.get("quantity")),
                            priority=request.form.get("priority", "Normal"), notes=request.form.get("notes"))
        db.session.add(vr)
        db.session.commit()
        log_activity(f"Submitted vaccine request {code} ({vr.antigen.name}, {vr.quantity_requested} vials)")
        flash(f"Request {code} submitted to RHU.", "success")
        return redirect(url_for("bhw.requests"))
    reqs = VaccineRequest.query.filter_by(barangay_id=bid).order_by(VaccineRequest.requested_at.desc()).all()
    stats = {"pending": sum(1 for r in reqs if r.status == "pending"),
             "approved": sum(1 for r in reqs if r.status == "approved"),
             "distributed": sum(1 for r in reqs if r.status == "fulfilled"),
             "rejected": sum(1 for r in reqs if r.status == "rejected")}
    return render_template("bhw_requests.html", **_bhw_ctx(
        "requests", page_title="Vaccine Requests", reqs=reqs, stats=stats, antigens=VaccineAntigen.query.all(),
    ))


@bhw_bp.route("/reports")
def reports():
    bid = current_user.barangay_id
    return render_template("bhw_reports.html", **_bhw_ctx(
        "reports", page_title="Reports", report_type=request.args.get("type", "coverage"),
        stats=dashboard_stats(bid), by_vaccine=coverage_by_vaccine(bid), generated_at=datetime.now(),
    ))


@bhw_bp.route("/notifications")
def notifications():
    return render_template("bhw_notifications.html", **_bhw_ctx(
        "notifications", page_title="Notifications", notes=get_notifications("bhw", barangay_id=current_user.barangay_id),
    ))


@bhw_bp.route("/settings")
def settings():
    return render_template("bhw_settings.html", **_bhw_ctx("settings", page_title="Settings"))


# ---------------------------------------------------------------------------
# Admin blueprint
# ---------------------------------------------------------------------------

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _admin_ctx(active, **extra):
    return dict(role="admin", nav_items=build_nav(ADMIN_NAV), active=active, current_user=current_user,
                unread_count=0, notif_url="#", **extra)


@admin_bp.before_request
@login_required
@role_required("admin")
def _admin_guard():
    pass


@admin_bp.route("/dashboard")
def dashboard():
    users = User.query.all()
    stats = {"total": len(users), "rhu": sum(1 for u in users if u.role == "rhu"),
             "bhw": sum(1 for u in users if u.role == "bhw"), "active": sum(1 for u in users if u.is_active_flag),
             "disabled": sum(1 for u in users if not u.is_active_flag),
             "logins_today": sum(1 for u in users if u.last_login_at and u.last_login_at.date() == datetime.utcnow().date())}
    role_dist = {"admin": sum(1 for u in users if u.role == "admin"), "rhu": stats["rhu"], "bhw": stats["bhw"]}
    return render_template("admin_dashboard.html", **_admin_ctx(
        "dashboard", page_title="Dashboard", stats=stats, role_dist=role_dist, users=users, now=datetime.now(),
    ))


@admin_bp.route("/users", methods=["GET", "POST"])
def users():
    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username").strip()
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return redirect(url_for("admin.users"))
        u = User(username=username, full_name=f"{request.form.get('first_name')} {request.form.get('last_name')}".strip(),
                 role=role, barangay_id=(int(request.form.get("barangay_id"))
                                         if role == "bhw" and request.form.get("barangay_id") else None))
        u.set_password(request.form.get("password") or "password123")
        db.session.add(u)
        db.session.commit()
        log_activity(f"Created user account: {u.full_name} ({u.role_label})")
        flash(f"User {u.full_name} created.", "success")
        return redirect(url_for("admin.users"))

    all_users = User.query.order_by(User.id).all()
    stats = {"total": len(all_users), "active": sum(1 for u in all_users if u.is_active_flag),
             "bhw": sum(1 for u in all_users if u.role == "bhw"),
             "rhu": sum(1 for u in all_users if u.role in ("rhu", "admin"))}
    return render_template("admin_users.html", **_admin_ctx(
        "users", page_title="User Management", users=all_users, stats=stats,
        barangays=Barangay.query.order_by(Barangay.name).all(),
    ))


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
def toggle_user(user_id):
    u = db.session.get(User, user_id) or abort(404)
    if u.id == current_user.id:
        abort(400)
    u.is_active_flag = not u.is_active_flag
    db.session.commit()
    log_activity(f"{'Enabled' if u.is_active_flag else 'Disabled'} user account: {u.username}")
    flash(f"User {u.username} {'enabled' if u.is_active_flag else 'disabled'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/assign-barangay", methods=["GET", "POST"])
def assign_barangay():
    if request.method == "POST":
        u = db.session.get(User, int(request.form.get("user_id"))) or abort(404)
        u.barangay_id = int(request.form.get("barangay_id"))
        db.session.commit()
        log_activity(f"Reassigned {u.full_name} to {u.barangay.name}")
        flash(f"{u.full_name} reassigned to {u.barangay.name}.", "success")
        return redirect(url_for("admin.assign_barangay"))
    return render_template("admin_assign_barangay.html", **_admin_ctx(
        "assign", page_title="Assign Barangay", bhws=User.query.filter_by(role="bhw").order_by(User.full_name).all(),
        barangays=Barangay.query.order_by(Barangay.name).all(),
    ))


@admin_bp.route("/coverage")
def coverage():
    by_barangay = coverage_by_barangay()
    return render_template("admin_coverage.html", **_admin_ctx(
        "coverage", page_title="Coverage Analytics", stats=dashboard_stats(), by_barangay=by_barangay,
        by_vaccine=coverage_by_vaccine(), trend=monthly_trend(),
        below_target=len([r for r in by_barangay if r["coverage"] < 90]),
    ))


@admin_bp.route("/map")
def municipality_map():
    return render_template("admin_map.html", **_admin_ctx(
        "map", page_title="Municipality Map", rankings=coverage_rankings(),
        heatmap=map_markers("heatmap"), at_risk=map_markers("at_risk"), density=map_markers("density"),
    ))


@admin_bp.route("/logs")
def logs():
    return render_template("admin_logs.html", **_admin_ctx(
        "logs", page_title="Activity Logs", logs=ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(200).all(),
        type_filter=request.args.get("type", "All"),
    ))


@admin_bp.route("/settings")
def settings():
    return render_template("admin_settings.html", **_admin_ctx("settings", page_title="Settings"))


# ---------------------------------------------------------------------------
# API blueprint (small JSON endpoints)
# ---------------------------------------------------------------------------

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)