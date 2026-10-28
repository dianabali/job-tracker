"""Job Application Tracker - Flask + SQLite."""
from datetime import date, datetime, timedelta
from collections import Counter

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tracker.db"
app.config["SECRET_KEY"] = "change-me"
db = SQLAlchemy(app)

STAGES = ["Wishlist", "Applied", "Interview", "Offer", "Rejected"]
INTERVIEW_TYPES = ["Phone screen", "Technical", "Take-home", "On-site", "Final", "Other"]


# ---------- models ----------
class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120))
    url = db.Column(db.String(400))
    salary = db.Column(db.String(60))          # posted range / expectation
    stage = db.Column(db.String(20), default="Wishlist", nullable=False)
    deadline = db.Column(db.Date)
    date_applied = db.Column(db.Date)
    offer_amount = db.Column(db.String(60))    # filled in when an offer arrives
    notes = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    contacts = db.relationship("Contact", backref="application", cascade="all, delete-orphan")
    interviews = db.relationship("Interview", backref="application", cascade="all, delete-orphan",
                                 order_by="Interview.when")

    @property
    def days_to_deadline(self):
        return (self.deadline - date.today()).days if self.deadline else None


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(120))
    email = db.Column(db.String(160))
    phone = db.Column(db.String(60))


class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    kind = db.Column(db.String(40), default="Phone screen")
    when = db.Column(db.DateTime, nullable=False)
    remind_hours = db.Column(db.Integer, default=24)  # show reminder this many hours before
    notes = db.Column(db.Text)
    done = db.Column(db.Boolean, default=False)


# ---------- helpers ----------
def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


def fill_application(a, form):
    a.company = form["company"].strip()
    a.role = form["role"].strip()
    a.location = form.get("location", "").strip()
    a.url = form.get("url", "").strip()
    a.salary = form.get("salary", "").strip()
    a.offer_amount = form.get("offer_amount", "").strip()
    a.notes = form.get("notes", "").strip()
    a.deadline = parse_date(form.get("deadline"))
    a.date_applied = parse_date(form.get("date_applied"))
    stage = form.get("stage", "Wishlist")
    a.stage = stage if stage in STAGES else "Wishlist"
    if a.stage == "Applied" and not a.date_applied:
        a.date_applied = date.today()


def reminders():
    """Upcoming interviews (inside their reminder window) and near deadlines."""
    now = datetime.now()
    items = []
    for i in Interview.query.filter_by(done=False).order_by(Interview.when).all():
        if i.when >= now - timedelta(hours=2) and i.when - now <= timedelta(hours=i.remind_hours):
            items.append(("interview", i.application, f"{i.kind} · {i.when:%a %d %b, %H:%M}"))
    soon = date.today() + timedelta(days=7)
    for a in Application.query.filter(Application.deadline != None,  # noqa: E711
                                      Application.deadline <= soon,
                                      Application.stage.in_(["Wishlist", "Applied"])).all():
        d = a.days_to_deadline
        label = "Deadline passed" if d < 0 else "Deadline today" if d == 0 else f"Deadline in {d}d"
        items.append(("deadline", a, label))
    return items


@app.context_processor
def inject():
    return {"stages": STAGES, "reminders": reminders(), "today": date.today()}


# ---------- board ----------
@app.route("/")
def board():
    q = request.args.get("q", "").strip()
    stage = request.args.get("stage", "")
    due = request.args.get("due", "")
    query = Application.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Application.company.ilike(like), Application.role.ilike(like),
                                 Application.location.ilike(like), Application.notes.ilike(like)))
    if stage in STAGES:
        query = query.filter_by(stage=stage)
    if due == "week":
        query = query.filter(Application.deadline != None,  # noqa: E711
                             Application.deadline <= date.today() + timedelta(days=7))
    apps = query.order_by(Application.deadline.is_(None), Application.deadline, Application.company).all()
    columns = {s: [a for a in apps if a.stage == s] for s in STAGES}
    return render_template("board.html", columns=columns, q=q, stage=stage, due=due)


@app.route("/applications/new", methods=["GET", "POST"])
def new_application():
    if request.method == "POST":
        a = Application()
        fill_application(a, request.form)
        db.session.add(a)
        db.session.commit()
        flash(f"Added {a.company}.")
        return redirect(url_for("detail", app_id=a.id))
    return render_template("form.html", a=None, default_stage=request.args.get("stage", "Wishlist"))


@app.route("/applications/<int:app_id>")
def detail(app_id):
    a = db.session.get(Application, app_id) or abort(404)
    return render_template("detail.html", a=a, types=INTERVIEW_TYPES, now=datetime.now())


@app.route("/applications/<int:app_id>/edit", methods=["GET", "POST"])
def edit_application(app_id):
    a = db.session.get(Application, app_id) or abort(404)
    if request.method == "POST":
        fill_application(a, request.form)
        db.session.commit()
        flash("Changes saved.")
        return redirect(url_for("detail", app_id=a.id))
    return render_template("form.html", a=a, default_stage=a.stage)


@app.post("/applications/<int:app_id>/delete")
def delete_application(app_id):
    a = db.session.get(Application, app_id) or abort(404)
    db.session.delete(a)
    db.session.commit()
    flash("Application deleted.")
    return redirect(url_for("board"))


@app.post("/applications/<int:app_id>/move")
def move(app_id):
    """Called by drag-and-drop on the board."""
    a = db.session.get(Application, app_id) or abort(404)
    stage = (request.get_json(silent=True) or {}).get("stage")
    if stage not in STAGES:
        return jsonify(error="bad stage"), 400
    a.stage = stage
    if stage == "Applied" and not a.date_applied:
        a.date_applied = date.today()
    db.session.commit()
    return jsonify(ok=True)


# ---------- contacts & interviews ----------
@app.post("/applications/<int:app_id>/contacts")
def add_contact(app_id):
    a = db.session.get(Application, app_id) or abort(404)
    f = request.form
    if f.get("name", "").strip():
        db.session.add(Contact(application_id=a.id, name=f["name"].strip(), title=f.get("title", "").strip(),
                               email=f.get("email", "").strip(), phone=f.get("phone", "").strip()))
        db.session.commit()
    return redirect(url_for("detail", app_id=a.id) + "#contacts")


@app.post("/contacts/<int:cid>/delete")
def delete_contact(cid):
    c = db.session.get(Contact, cid) or abort(404)
    app_id = c.application_id
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for("detail", app_id=app_id) + "#contacts")


@app.post("/applications/<int:app_id>/interviews")
def add_interview(app_id):
    a = db.session.get(Application, app_id) or abort(404)
    f = request.form
    try:
        when = datetime.strptime(f["when"], "%Y-%m-%dT%H:%M")
    except (KeyError, ValueError):
        flash("Pick a valid date and time for the interview.")
        return redirect(url_for("detail", app_id=a.id) + "#interviews")
    db.session.add(Interview(application_id=a.id, kind=f.get("kind", "Other"), when=when,
                             remind_hours=int(f.get("remind_hours") or 24), notes=f.get("notes", "").strip()))
    if a.stage in ("Wishlist", "Applied"):
        a.stage = "Interview"
    db.session.commit()
    return redirect(url_for("detail", app_id=a.id) + "#interviews")


@app.post("/interviews/<int:iid>/update")
def update_interview(iid):
    i = db.session.get(Interview, iid) or abort(404)
    i.notes = request.form.get("notes", "").strip()
    i.done = "done" in request.form
    db.session.commit()
    flash("Interview notes saved.")
    return redirect(url_for("detail", app_id=i.application_id) + f"#interview-{i.id}")


@app.post("/interviews/<int:iid>/delete")
def delete_interview(iid):
    i = db.session.get(Interview, iid) or abort(404)
    app_id = i.application_id
    db.session.delete(i)
    db.session.commit()
    return redirect(url_for("detail", app_id=app_id) + "#interviews")


# ---------- stats ----------
@app.route("/stats")
def stats():
    apps = Application.query.all()
    total = len(apps)
    counts = Counter(a.stage for a in apps)
    submitted = [a for a in apps if a.stage != "Wishlist"]
    responded = [a for a in submitted if a.stage in ("Interview", "Offer", "Rejected") or a.interviews]
    interviewed = [a for a in apps if a.stage in ("Interview", "Offer") or a.interviews]
    offers = counts["Offer"]

    def pct(n, d):
        return round(100 * n / d) if d else 0

    # applications submitted per week, last 8 weeks
    monday = date.today() - timedelta(days=date.today().weekday())
    weeks = []
    for k in range(7, -1, -1):
        start = monday - timedelta(weeks=k)
        n = sum(1 for a in submitted if a.date_applied and start <= a.date_applied < start + timedelta(days=7))
        weeks.append((start.strftime("%d %b"), n))

    return render_template("stats.html", total=total, counts=counts, submitted=len(submitted),
                           response_rate=pct(len(responded), len(submitted)),
                           interview_rate=pct(len(interviewed), len(submitted)),
                           offer_rate=pct(offers, len(submitted)), weeks=weeks,
                           max_week=max([n for _, n in weeks] + [1]),
                           upcoming=Interview.query.filter(Interview.when >= datetime.now(), Interview.done == False)  # noqa: E712
                           .order_by(Interview.when).limit(5).all())


@app.cli.command("seed")
def seed():
    """flask seed - add a few sample applications."""
    db.create_all()
    t = date.today()
    rows = [("Northwind", "Backend Engineer", "Wishlist", t + timedelta(days=4), None),
            ("Globex", "Python Developer", "Applied", t + timedelta(days=12), t - timedelta(days=5)),
            ("Initech", "Full-stack Engineer", "Interview", None, t - timedelta(days=14)),
            ("Umbrella Labs", "Data Engineer", "Offer", None, t - timedelta(days=30)),
            ("Hooli", "SRE", "Rejected", None, t - timedelta(days=21))]
    for c, r, s, dl, ap in rows:
        db.session.add(Application(company=c, role=r, stage=s, deadline=dl, date_applied=ap))
    db.session.commit()
    print("Seeded.")


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
