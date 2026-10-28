# Job Application Tracker

Flask + SQLite. Kanban board, interview notes and reminders, contacts, search/filters, statistics.

    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    flask --app app seed      # optional sample data
    flask --app app run --debug

Open http://127.0.0.1:5000. Data is stored in `instance/tracker.db`.
Set a real `SECRET_KEY` in `app.py` before deploying anywhere public.
