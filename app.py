import os, io, base64
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, select, and_, text
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone
from calendar import monthrange

from models import Base, State, Log, Progress, WorkoutSession, Settings 
from logic import DAYS, COMPOUND_RM_MAP, round_to_2p5, compute_new_load

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.db")
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800
)

_db_ready = False
def ensure_db():
    """Connect once and create tables lazily."""
    global _db_ready
    if _db_ready:
        return
    with engine.connect() as conn:
        conn.execute(text("select 1"))
    Base.metadata.create_all(engine)
    _db_ready = True

app = Flask(__name__)

@app.route("/healthz")
def healthz():
    try:
        ensure_db()
        return "ok", 200
    except Exception as e:
        return f"db error: {e}", 500
    
@app.route("/rm-test-health")
def rm_test_health():
    ensure_db()
    with Session(engine) as s:
        st = s.get(Settings, 1)
        if st is None:
            return {"ok": False, "reason": "Settings row missing"}, 200
        return {
            "ok": True,
            "units": st.units,
            "bench_kg": st.bench,
            "squat_kg": st.squat,
            "deadlift_kg": st.deadlift,
            "ohp_kg": st.ohp,
        }, 200

app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

# --- helpers for week-1/2 suggested loads from RM Test ---
def _percent_for_week(week: int) -> float:
    # tweak if you prefer (e.g., 0.70/0.75). These are good conservative starts.
    return 0.55 if week == 1 else 0.675

def _round_kg_to_2p5(x: float) -> float:
    # storage is kg; round to nearest 2.5 kg for plates
    return round(x / 2.5) * 2.5

def seed_from_rms_for_row(row, st, week: int, rm_map: dict):
    """
    If this exercise maps to an RM and week is 1 or 2,
    seed row.load_last from st.<rm> * pct (rounded) IF it's empty.
    """
    if row.load_last not in (None, 0) and row.load_last is not None:
        return  # already seeded / logged

    if week not in (1, 2):
        return

    rm_key = rm_map.get(row.exercise)
    if not rm_key:
        return  # no RM mapping for this exercise (e.g., accessories)

    one_rm = getattr(st, rm_key, None)
    if not one_rm:
        return  # user hasn't set this RM yet

    pct = _percent_for_week(week)
    load_kg = _round_kg_to_2p5(one_rm * pct)
    row.load_last = load_kg

# ------------ 1RM estimation (Epley) and updater ------------
def epley_1rm(weight_kg: float, reps: int) -> float:
    """
    Epley: 1RM ≈ w * (1 + reps/30). Returns kg. Requires reps >= 1 and weight > 0.
    """
    if not weight_kg or weight_kg <= 0 or not reps or reps < 1:
        return 0.0
    return weight_kg * (1.0 + reps / 30.0)

# Map exercises to which Settings 1RM they influence
ESTIMATED_RM_MAP = {
    # Squat
    "Back Squat": "squat",

    # Bench (barbell focus; include close-grip as a conservative bench estimator)
    "Flat Barbell Bench Press": "bench",
    "Close-Grip Bench Press": "bench",

    # Overhead Press
    "Overhead Press (Barbell/DB)": "ohp",
    "Seated DB Overhead Press": "ohp",

    # Deadlift
    "Deadlift": "deadlift",
}

def update_1rms_from_rows(settings_obj, log_rows):
    """
    Scan this POST's rows for best Epley estimates per lift type, compare to stored 1RMs,
    and update + return a list of (lift_name, old_kg, new_kg) when a PR is detected.
    """
    best_est = {"bench": 0.0, "squat": 0.0, "deadlift": 0.0, "ohp": 0.0}

    # For each row, use the highest reps among S1..S3 at the "load_last" *this week*.
    for r in log_rows:
        rm_key = ESTIMATED_RM_MAP.get(r.exercise)
        if not rm_key:
            continue

        reps_candidates = [r.s1 or 0, r.s2 or 0, r.s3 or 0]
        max_reps = max(reps_candidates) if reps_candidates else 0
        if not max_reps or not r.load_last:
            continue

        est = epley_1rm(r.load_last, max_reps)
        if est > best_est[rm_key]:
            best_est[rm_key] = est

    # Compare to stored and update any PRs
    pr_list = []
    for key in ["bench", "squat", "deadlift", "ohp"]:
        current = getattr(settings_obj, key, None) or 0.0
        if best_est[key] > current:
            pr_list.append((key, current, best_est[key]))
            setattr(settings_obj, key, best_est[key])

    return pr_list

def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        pw = os.environ.get("PASSWORD")
        if pw and not session.get("authed"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def get_or_create_state(s: Session) -> State:
    st = s.scalars(select(State)).first()
    if not st:
        st = State(units="kg", rms={"squat": None, "bench": None, "deadlift": None, "ohp": None})
        s.add(st); s.commit(); s.refresh(st)
    return st

def init_week_rows(week: int, s: Session):
    """
    Ensure all rows for this week exist and metadata matches the active program.
    Does NOT overwrite user loads/reps; only seeds Week 1/2 suggested loads from RM Test.
    """
    from logic import DAYS, COMPOUND_RM_MAP  # DAYS = PROGRAM_V1 list

    st = get_or_create_state(s)

    for day_idx, (day_title, exercises) in enumerate(DAYS, start=1):
        for ex_name, sets, rep_low, rep_high, category, increment in exercises:
            row = s.scalars(
                select(Log).where(
                    Log.week == week,
                    Log.day == day_idx,
                    Log.exercise == ex_name,
                )
            ).first()

            if row is None:
                row = Log(
                    week=week, day=day_idx, day_title=day_title,
                    exercise=ex_name, sets=sets, rep_low=rep_low, rep_high=rep_high,
                    category=category, increment=increment,
                    load_last=None, new_load=None
                )
                # seed suggested for week 1/2 if RM exists
                seed_from_rms_for_row(row, st, week, COMPOUND_RM_MAP)
                s.add(row)
            else:
                # keep metadata in sync with program
                row.day_title = day_title
                row.sets = sets
                row.rep_low = rep_low
                row.rep_high = rep_high
                row.category = category
                row.increment = increment
                # clear stale AMRAP if now a compound
                if row.category != "accessory":
                    row.amrap = None
                # if Week 1/2 and still blank, try to seed suggested load
                if row.load_last in (None, 0):
                    seed_from_rms_for_row(row, st, week, COMPOUND_RM_MAP)

    s.commit()

@app.template_filter("b64encode")
def b64encode_filter(data: bytes):
    return base64.b64encode(data).decode("ascii") if data else ""

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        pw = os.environ.get("PASSWORD")
        if not pw or request.form.get("password") == pw:
            session["authed"] = True
            flash("Logged in.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Wrong password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("dashboard"))

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/settings", methods=["GET","POST"])
@require_login
def settings():
    ensure_db()
    with Session(engine) as s:
        st = get_or_create_state(s)
        if request.method == "POST":
            units = request.form.get("units","kg")
            st.units = "lb" if units=="lb" else "kg"
            s.commit()
            flash("Settings saved.", "success")
            return redirect(url_for("settings"))
        return render_template("settings.html", state={"units": st.units})

@app.route("/history")
@require_login
def history():
    ensure_db()
    with Session(engine) as s:
        today = date.today()
        y = int(request.args.get("y", today.year))
        m = int(request.args.get("m", today.month))
        days_in_month = monthrange(y, m)[1]

        # Python computes weekday of the 1st: Monday=0..Sunday=6; we want Sunday-first grids
        first_weekday_mon0 = date(y, m, 1).weekday()  # 0..6 (Mon..Sun)
        start_pad = (first_weekday_mon0 + 1) % 7  # 0..6 (Sun..Sat), # of blanks before day 1

        sessions = s.scalars(
            select(WorkoutSession).where(
                WorkoutSession.session_date >= date(y, m, 1),
                WorkoutSession.session_date <= date(y, m, days_in_month),
            ).order_by(WorkoutSession.session_date)
        ).all()
        by_day = {}
        for sess in sessions:
            by_day.setdefault(sess.session_date.day, []).append(sess)

        return render_template("history.html",
                               year=y, month=m, days=days_in_month,
                               start_pad=start_pad, by_day=by_day)

@app.route("/history/<int:y>/<int:m>/<int:d>")
@require_login
def history_day(y, m, d):
    ensure_db()
    with Session(engine) as s:
        sess = s.scalars(
            select(WorkoutSession).where(WorkoutSession.session_date == date(y, m, d))
        ).first()
        if not sess:
            flash("No workout found for that date.", "error")
            return redirect(url_for("history", y=y, m=m))

        rows = s.scalars(select(Log).where(Log.week == sess.week, Log.day == sess.day)).all()
        st = get_or_create_state(s)
        def show_w(x): return None if x is None else (round(x*2.20462262185,2) if st.units=="lb" else x)
        for r in rows:
            r.load_last = show_w(r.load_last)
            r.new_load = show_w(r.new_load)

        return render_template("history_day.html", sess=sess, rows=rows, units=st.units)

@app.route("/rm-test", methods=["GET", "POST"])
@require_login
def rm_test():
    """
    Robust RM Test page:
    - Creates a Settings row if missing.
    - Stores bench/squat/deadlift/ohp in kg.
    - On GET, shows current values in user's units (kg/lb).
    - On POST, saves values and re-seeds week 1 & 2 suggested loads.
    """
    ensure_db()
    with Session(engine) as s:
        # ---- get or create Settings row safely (no external helpers) ----
        st = s.get(Settings, 1)
        if st is None:
            st = Settings(
                id=1,
                units="kg",          # default to kg
                bench=None,
                squat=None,
                deadlift=None,
                ohp=None,
            )
            s.add(st)
            s.commit()

        # convenience converters based on current units
        def to_display(x):
            if x is None:
                return ""
            return round(x * 2.20462262185, 2) if st.units == "lb" else round(x, 2)

        def to_kg(x):
            if x is None:
                return None
            return x if st.units == "kg" else x / 2.20462262185

        if request.method == "POST":
            # parse numeric inputs in user units (kg or lb)
            def p(name):
                v = request.form.get(name)
                if v in (None, ""):
                    return None
                try:
                    return float(v)
                except Exception:
                    return None

            bench_in = p("bench_rm")
            squat_in = p("squat_rm")
            dead_in  = p("deadlift_rm")
            ohp_in   = p("ohp_rm")

            # store as kg (only overwrite if user supplied a value)
            if bench_in is not None:   st.bench    = to_kg(bench_in)
            if squat_in is not None:   st.squat    = to_kg(squat_in)
            if dead_in  is not None:   st.deadlift = to_kg(dead_in)
            if ohp_in   is not None:   st.ohp      = to_kg(ohp_in)

            s.commit()

            # try to ensure weeks 1 & 2 exist and have suggested loads seeded
            try:
                init_week_rows(1, s)
                init_week_rows(2, s)
                s.commit()
            except Exception:
                # don't fail the page if seeding hiccups; you can still go to /week/1
                pass

            flash("1RM values saved.", "success")
            return redirect(url_for("week_view", week=1))

        # GET: render with current values (in the user's units)
        ctx = {
            "units": st.units or "kg",
            "bench_disp": to_display(st.bench),
            "squat_disp": to_display(st.squat),
            "deadlift_disp": to_display(st.deadlift),
            "ohp_disp": to_display(st.ohp),
        }
        return render_template("rm_test.html", **ctx)

@app.route("/week/<int:week>", methods=["GET", "POST"])
@require_login
def week_view(week: int):
    ensure_db()

    if week < 1 or week > 12:
        flash("Week must be 1–12.", "error")
        return redirect(url_for("dashboard"))

    with Session(engine) as s:
        st = get_or_create_state(s)
        init_week_rows(week, s)  # seeds Program V1.0 rows if missing, syncs metadata if you added that

        if request.method == "POST":
            # -------- Daily Save & timer (one day at a time via modal) --------
            save_day = request.form.get("save_day")
            if save_day:
                day_int = int(save_day)
                # timer fields
                start_iso = request.form.get(f"start_{day_int}")
                end_iso   = request.form.get(f"end_{day_int}")

                started_at = ended_at = None
                duration_seconds = None
                try:
                    if start_iso:
                        started_at = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                    if end_iso:
                        ended_at = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                    if started_at and ended_at:
                        duration_seconds = int((ended_at - started_at).total_seconds())
                except Exception:
                    pass

                # record a session row for today
                today = datetime.now(timezone.utc).date()
                sess = s.execute(
                    select(WorkoutSession).where(
                        WorkoutSession.week == week,
                        WorkoutSession.day == day_int,
                        WorkoutSession.session_date == today,
                    )
                ).scalar_one_or_none()

                if sess is None:
                    sess = WorkoutSession(
                        week=week, day=day_int, session_date=today,
                        started_at=started_at, ended_at=ended_at,
                        duration_seconds=duration_seconds
                    )
                    s.add(sess)
                else:
                    if started_at: sess.started_at = started_at
                    if ended_at:   sess.ended_at = ended_at
                    if duration_seconds is not None:
                        sess.duration_seconds = duration_seconds

            # -------- Bodyweight (stored in kg) --------
            bw = request.form.get("bodyweight")
            if bw not in (None, ""):
                try:
                    bw_val = float(bw)
                    bw_kg = bw_val if st.units == "kg" else bw_val / 2.20462262185
                    existing = s.scalars(select(Progress).where(Progress.week == week)).first()
                    if existing:
                        existing.bodyweight = bw_kg
                    else:
                        s.add(Progress(week=week, bodyweight=bw_kg))
                except Exception:
                    pass

            # -------- Parse all inputs for the week, compute progression --------
            rows = s.scalars(select(Log).where(Log.week == week)).all()
            for r in rows:
                # Load (this week) — base for progression; store as kg
                load_field = request.form.get(f"row_{r.id}_load")
                if load_field not in (None, ""):
                    try:
                        load_val = float(load_field)
                        load_kg = load_val if st.units == "kg" else load_val / 2.20462262185
                        r.load_last = load_kg
                    except Exception:
                        pass

                # Reps (S1–S3)
                for k in ["s1", "s2", "s3"]:
                    val = request.form.get(f"row_{r.id}_{k}")
                    if val not in (None, ""):
                        try: setattr(r, k, int(val))
                        except Exception: setattr(r, k, None)

                # Treat S3 as AMRAP for accessories; ignore AMRAP separately
                amrap_reps = r.s3 if r.category == "accessory" else None

                data = {
                    "load_last": r.load_last,
                    "rep_high": r.rep_high,
                    "increment": r.increment,
                    "category": r.category,
                    "sets": r.sets,
                    "s1": r.s1, "s2": r.s2, "s3": r.s3,
                    "amrap": amrap_reps
                }
                r.new_load = compute_new_load(data)

            s.commit()
            flash(f"Week {week} saved.", "success")
            return redirect(url_for("week_view", week=week))

        # -------- GET render --------
        rows = s.scalars(
            select(Log).where(Log.week == week).order_by(Log.day, Log.id)
        ).all()

        def display_w(x):
            if x is None:
                return None
            return round(x * 2.20462262185, 2) if st.units == "lb" else x

        grouped = []
        for day_idx in range(1, 8):
            sub = [r for r in rows if r.day == day_idx]
            title = sub[0].day_title if sub else f"Day {day_idx}"
            for r in sub:
                r.load_last = display_w(r.load_last)
                r.new_load = display_w(r.new_load)
            grouped.append((title, sub))

        # Bodyweight (display units)
        bw_val = None
        prog = s.scalars(select(Progress).where(Progress.week == week)).first()
        if prog:
            bw_val = prog.bodyweight if st.units == "kg" else round(prog.bodyweight * 2.20462262185, 1)

        return render_template("week.html", week=week, grouped=grouped, bw=bw_val, units=st.units)

@app.route("/dashboard")
@require_login
def dashboard():
    ensure_db()
    with Session(engine) as s:
        st = get_or_create_state(s)
        # BW chart
        progs = s.scalars(select(Progress).order_by(Progress.week)).all()
        fig, ax = plt.subplots(figsize=(7,3))
        if progs:
            x = [p.week for p in progs]
            y = [p.bodyweight if st.units=='kg' else p.bodyweight*2.20462262185 for p in progs]
            ax.plot(x, y)
            ax.set_ylabel(f"Body Weight ({st.units})")
        ax.set_xlabel("Week"); ax.grid(True, alpha=0.3)
        bio = io.BytesIO(); fig.tight_layout(); fig.savefig(bio, format="png", dpi=110); plt.close(fig); bio.seek(0)
        bw_png = bio.read()

        # Lift charts
        lifts = ["Back Squat","Flat Barbell Bench Press","Deadlift","Overhead Press (Barbell/DB)"]
        lift_pngs = {}
        for lift in lifts:
            series = s.execute(select(Log.week, Log.new_load, Log.load_last).where(Log.exercise==lift).order_by(Log.week)).all()
            if not series: continue
            weeks = [w for (w,_,_) in series]
            loads = [(nl if nl is not None else ll) for (_,nl,ll) in series]
            loads = [ (l*2.20462262185 if (l is not None and st.units=='lb') else l) for l in loads ]
            fig2, ax2 = plt.subplots(figsize=(7,3))
            ax2.plot(weeks, loads); ax2.set_xlabel("Week"); ax2.set_ylabel(f"{lift} ({st.units})")
            ax2.grid(True, alpha=0.3)
            bio2 = io.BytesIO(); fig2.tight_layout(); fig2.savefig(bio2, format="png", dpi=110); plt.close(fig2); bio2.seek(0)
            lift_pngs[lift] = bio2.read()

        return render_template("dashboard.html", bw_png=bw_png, lift_pngs=lift_pngs, units=st.units)

@app.route("/export.xlsx")
@require_login
def export_xlsx():
    ensure_db()
    with Session(engine) as s:
        logs = s.scalars(select(Log)).all()
        prog = s.scalars(select(Progress)).all()
        df_logs = pd.DataFrame([{
            "week": r.week, "day": r.day, "day_title": r.day_title, "exercise": r.exercise,
            "sets": r.sets, "rep_low": r.rep_low, "rep_high": r.rep_high, "category": r.category,
            "increment": r.increment, "load_last": r.load_last, "s1": r.s1, "s2": r.s2, "s3": r.s3,
            "amrap": r.amrap, "new_load": r.new_load, "notes": r.notes
        } for r in logs])
        df_prog = pd.DataFrame([{"week": p.week, "bodyweight": p.bodyweight} for p in prog])
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as w:
            (df_logs if not df_logs.empty else pd.DataFrame()).to_excel(w, sheet_name="log", index=False)
            (df_prog if not df_prog.empty else pd.DataFrame()).to_excel(w, sheet_name="progress", index=False)
        bio.seek(0)
        return send_file(bio, as_attachment=True, download_name="hypertrophy_export.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
