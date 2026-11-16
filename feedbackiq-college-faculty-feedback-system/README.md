# FeedbackIQ — College Faculty Feedback Management System

FeedbackIQ is a role-based web application for collecting student feedback about faculty members and presenting faculty-level and institution-level feedback summaries.

It provides separate experiences for students, faculty members and administrators.

## Features

### Student portal
- Sign in with an institution-created account.
- Select a faculty member.
- Submit a 1–5 rating and an optional written comment.
- Feedback records do not store a student identifier, so the submitted feedback is anonymous within this application's feedback table.

### Faculty portal
- View the faculty member's own average rating and review count.
- See rating distribution.
- Read recent written comments associated with their faculty profile.

### Administrator portal
- View faculty profiles and departments.
- Compare review counts and average ratings.
- See total feedback submissions and the highest-rated faculty member among profiles with feedback.

## Technology

- Python 3.10+
- Flask
- SQLite
- Jinja2
- HTML
- Tailwind CSS (loaded from the Tailwind CDN)

## Project structure

```text
feedbackiq-college-faculty-feedback-system/
├── app.py
├── database.sql
├── requirements.txt
├── requirements-prod.txt
├── Procfile
├── .env.example
├── .gitignore
├── instance/                 # Local database; ignored by Git
└── templates/
    ├── base.html
    ├── login.html
    ├── student.html
    ├── faculty.html
    ├── admin.html
    └── error.html
```

## Run locally

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux / Codespaces:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and replace `SECRET_KEY` with a long random value.

Generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit `.env`.

### 4. Create the database

The application creates its SQLite schema automatically on startup. You can also run:

```bash
flask --app app init-db
```

### 5. Create accounts

There are deliberately no public default credentials or seeded accounts. Create an administrator account first:

```bash
flask --app app create-user --role admin
```

Then create a student account:

```bash
flask --app app create-user --role student
```

Create a faculty account with a linked faculty profile:

```bash
flask --app app create-user --role faculty --name "Faculty Name" --department "Computer Science"
```

The CLI prompts for a password and stores a password hash, not the original password. Use a unique password of at least 10 characters.

### 6. Start the development server

```bash
python app.py
```

Open http://127.0.0.1:5000.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Deploying

For a production deployment:

1. Use a managed hosting platform that supports Python web applications.
2. Set a strong `SECRET_KEY` environment variable in the host dashboard.
3. Set `COOKIE_SECURE=1` when the application is served over HTTPS.
4. Use `requirements-prod.txt` and the included `Procfile` for a Gunicorn-based host.
5. Attach persistent storage for the SQLite database, or migrate to a managed PostgreSQL database for multi-instance deployments.
6. Back up the database and restrict access to administrative accounts.
7. Review privacy, retention, consent and institutional policies before collecting real student feedback.

SQLite is suitable for a small demonstration or single-instance deployment. For a multi-user institutional production system, a managed database such as PostgreSQL is recommended.

## Security notes

- Passwords are hashed with Werkzeug's password hashing utilities.
- Forms use CSRF protection.
- Sessions use HTTP-only cookies and SameSite=Lax.
- Session cookies can be configured as Secure for HTTPS deployments.
- Role checks protect student, faculty and administrator routes.
- SQL statements use parameterized queries.
- Local databases, environment files and Python cache files are excluded by `.gitignore`.
- No default accounts or passwords are seeded automatically.

This project is an academic/portfolio prototype, not a certified student information system. Before institutional use, add formal account provisioning, audit logging, backups, stronger operational monitoring, privacy controls and security review.

## Current scope and limitations

- Accounts are provisioned by an administrator using the Flask CLI; there is no public self-registration or password-reset workflow.
- Feedback is anonymous in the feedback table because it does not contain a student ID. The application does not claim cryptographic anonymity or protect against identification through operational logs or external processes.
- Faculty can see comments and ratings associated with their own profile.
- Administrator analytics are based on submitted ratings and should not be treated as a complete or objective measure of teaching quality.
- The current app does not include appointment scheduling, attendance, messaging, LMS integration or automated report exports.

## Suggested GitHub topics

`college-feedback-system` · `faculty-feedback` · `student-feedback` · `feedback-management` · `python` · `flask` · `sqlite` · `education-technology` · `academic-analytics` · `faculty-performance`

## License

No license is included yet. Choose a license only after deciding how you want others to use, modify and redistribute the project.
