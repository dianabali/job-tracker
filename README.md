# Job Application Tracker

A self-hosted web app for keeping a job search organized. Track every application on a Kanban board, log interview notes, keep recruiter contacts in one place, and see how your search is going.

Built with **Flask**, **SQLite** and plain HTML/CSS. The only JavaScript is the small drag-and-drop script on the board, so there is no build step and no frontend dependencies.

## Features

**Kanban board**
- Five stages: Wishlist, Applied, Interview, Offer, Rejected
- Drag a card to another column and the new stage is saved immediately
- Cards show the role, location, deadline and next scheduled interview
- Deadline chips turn amber within 7 days and red once overdue

**Interviews and reminders**
- Schedule any number of interviews per application (phone screen, technical, take-home, on-site, final)
- Choose a reminder window: 2 hours, 1 day or 3 days before
- Keep notes for each interview and mark it completed
- A banner on every page lists interviews inside their reminder window and deadlines due within a week
- Scheduling an interview moves a Wishlist or Applied card to Interview

**Contacts and offers**
- Save recruiters and hiring managers (name, title, email, phone) against each application
- Record the offer amount alongside the posted salary range

**Search, filters and statistics**
- Search company, role, location and notes
- Filter by stage or by deadlines due within 7 days
- Statistics page with response, interview and offer rates, a breakdown by stage, applications submitted per week, and upcoming interviews

The interface follows your system's light or dark theme.

## Quick start

Requires Python 3.9 or newer.

```bash
git clone https://github.com/dianabali/job-tracker.git
cd job-tracker

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

flask --app app seed  # optional: load sample applications
flask --app app run --debug
```

Open <http://127.0.0.1:5000>.

The database is created automatically on first run and stored in `instance/tracker.db`. To start fresh, delete that file.

## How the statistics are calculated

| Metric | Definition |
| --- | --- |
| Submitted | Every application not in Wishlist |
| Heard back | Submitted applications that reached Interview, Offer or Rejected, or have an interview logged |
| Reached interview | Submitted applications in Interview or Offer, or with an interview logged |
| Got an offer | Applications in Offer, as a share of submitted |

Each rate is a percentage of submitted applications.

## Project structure

```
job-tracker/
├── app.py              # models, routes and statistics
├── requirements.txt
├── static/
│   └── style.css
└── templates/
    ├── base.html       # layout, navigation, reminder banner
    ├── board.html      # Kanban board, filters, drag and drop
    ├── detail.html     # one application: details, interviews, contacts
    ├── form.html       # create and edit form
    └── stats.html
```

### Data model

| Model | Key fields |
| --- | --- |
| `Application` | company, role, location, url, salary, stage, deadline, date_applied, offer_amount, notes |
| `Interview` | kind, when, remind_hours, notes, done |
| `Contact` | name, title, email, phone |

Interviews and contacts belong to an application and are deleted with it.

### Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Board. Accepts `q`, `stage` and `due=week` query parameters |
| GET, POST | `/applications/new` | Create an application |
| GET | `/applications/<id>` | Application detail |
| GET, POST | `/applications/<id>/edit` | Edit an application |
| POST | `/applications/<id>/delete` | Delete an application |
| POST | `/applications/<id>/move` | Change stage (JSON body `{"stage": "Offer"}`), used by drag and drop |
| POST | `/applications/<id>/contacts` | Add a contact |
| POST | `/applications/<id>/interviews` | Schedule an interview |
| POST | `/interviews/<id>/update` | Save notes and completion |
| GET | `/stats` | Statistics |

## Configuration

Settings live at the top of `app.py`:

- `SECRET_KEY` is a placeholder. Change it before deploying anywhere other than your own machine.
- `SQLALCHEMY_DATABASE_URI` defaults to a local SQLite file.
- `STAGES` and `INTERVIEW_TYPES` control the board columns and interview types. Edit these lists to rename or add options.
