import os
import sqlite3
import secrets
from pathlib import Path
from functools import wraps

import click
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DEFAULT_DB = INSTANCE_DIR / "feedbackiq.sqlite3"


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(INSTANCE_DIR), instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("DATABASE_PATH", str(DEFAULT_DB)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    CSRFProtect(app)

    def get_db():
        if "db" not in g:
            db_path = Path(app.config["DATABASE"])
            db_path.parent.mkdir(parents=True, exist_ok=True)
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
            g.db.execute("PRAGMA journal_mode = WAL")
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','faculty','student')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comments TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_faculty_created
            ON feedback(faculty_id, created_at DESC);
        """)
        db.commit()

    app.teardown_appcontext  # keep the teardown registration visible to Flask

    def login_required(role=None):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if not session.get("user_id"):
                    flash("Please sign in to continue.", "error")
                    return redirect(url_for("login"))
                if role and session.get("role") != role:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.route("/", methods=["GET", "POST"])
    def login():
        if session.get("user_id"):
            return redirect(url_for(session.get("role", "login")))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not username or not password:
                flash("Enter both username and password.", "error")
            else:
                user = get_db().execute(
                    "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                    (username,),
                ).fetchone()
                if user and check_password_hash(user["password_hash"], password):
                    session.clear()
                    session.permanent = True
                    session["user_id"] = user["id"]
                    session["user"] = user["username"]
                    session["role"] = user["role"]
                    return redirect(url_for(user["role"]))
                flash("Invalid username or password.", "error")
        return render_template("login.html")

    @app.route("/student", methods=["GET", "POST"])
    @login_required("student")
    def student():
        db = get_db()
        if request.method == "POST":
            try:
                faculty_id = int(request.form.get("faculty_id", ""))
                rating = int(request.form.get("rating", ""))
            except (TypeError, ValueError):
                flash("Choose a faculty member and a valid rating.", "error")
                return redirect(url_for("student"))

            comments = request.form.get("comments", "").strip()
            if not db.execute("SELECT 1 FROM faculty WHERE id = ?", (faculty_id,)).fetchone():
                flash("The selected faculty member could not be found.", "error")
            elif rating not in range(1, 6):
                flash("Rating must be between 1 and 5.", "error")
            elif len(comments) > 1500:
                flash("Comments must be 1,500 characters or fewer.", "error")
            else:
                db.execute(
                    "INSERT INTO feedback (faculty_id, rating, comments) VALUES (?, ?, ?)",
                    (faculty_id, rating, comments or None),
                )
                db.commit()
                flash("Feedback submitted successfully. Thank you!", "success")
                return redirect(url_for("student"))

        faculty = db.execute(
            "SELECT id, name, department FROM faculty ORDER BY department, name"
        ).fetchall()
        return render_template("student.html", faculty=faculty)

    @app.route("/faculty")
    @login_required("faculty")
    def faculty():
        db = get_db()
        profile = db.execute(
            "SELECT id, name, department FROM faculty WHERE user_id = ?",
            (session["user_id"],),
        ).fetchone()
        if not profile:
            abort(403)

        stats = db.execute(
            "SELECT ROUND(AVG(rating), 2) AS avg, COUNT(*) AS total "
            "FROM feedback WHERE faculty_id = ?", (profile["id"],)
        ).fetchone()
        dist_rows = db.execute(
            "SELECT rating, COUNT(*) AS cnt FROM feedback "
            "WHERE faculty_id = ? GROUP BY rating", (profile["id"],)
        ).fetchall()
        dist = {row["rating"]: row["cnt"] for row in dist_rows}
        feedback = db.execute(
            "SELECT rating, comments, created_at FROM feedback "
            "WHERE faculty_id = ? ORDER BY created_at DESC LIMIT 100",
            (profile["id"],),
        ).fetchall()
        return render_template(
            "faculty.html", faculty=profile, avg=stats["avg"], total=stats["total"],
            dist=dist, feedback=feedback,
        )

    @app.route("/admin")
    @login_required("admin")
    def admin():
        db = get_db()
        stats = db.execute("""
            SELECT f.id, f.name, f.department,
                   COUNT(fb.id) AS total,
                   ROUND(AVG(fb.rating), 2) AS avg
            FROM faculty f
            LEFT JOIN feedback fb ON f.id = fb.faculty_id
            GROUP BY f.id, f.name, f.department
            ORDER BY CASE WHEN AVG(fb.rating) IS NULL THEN 1 ELSE 0 END,
                     AVG(fb.rating) DESC, COUNT(fb.id) DESC, f.name ASC
        """).fetchall()
        total_feedback = db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        overall_avg = db.execute("SELECT ROUND(AVG(rating), 2) FROM feedback").fetchone()[0]
        top_faculty = next((row["name"] for row in stats if row["avg"] is not None), "N/A")
        return render_template(
            "admin.html", stats=stats, total_fb=total_feedback,
            overall_avg=overall_avg if overall_avg is not None else "N/A",
            top_faculty=top_faculty,
        )

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The page you requested could not be found."), 404

    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables."""
        with app.app_context():
            init_db()
        click.echo("Database initialized.")

    @app.cli.command("create-user")
    @click.option("--username", prompt=True)
    @click.option("--role", type=click.Choice(["admin", "student", "faculty"]), prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--name", default="", help="Required for faculty accounts.")
    @click.option("--department", default="", help="Required for faculty accounts.")
    def create_user_command(username, role, password, name, department):
        """Create a user account without storing a plaintext password."""
        username = username.strip()
        if len(username) < 3 or len(username) > 40:
            raise click.ClickException("Username must be between 3 and 40 characters.")
        if len(password) < 10:
            raise click.ClickException("Use a password with at least 10 characters.")
        if role == "faculty" and (not name.strip() or not department.strip()):
            raise click.ClickException("Faculty accounts require --name and --department.")
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
            )
            if role == "faculty":
                db.execute(
                    "INSERT INTO faculty (user_id, name, department) VALUES (?, ?, ?)",
                    (cursor.lastrowid, name.strip(), department.strip()),
                )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            raise click.ClickException("That username already exists.")
        click.echo(f"Created {role} account: {username}")

    with app.app_context():
        init_db()

    return app


app = create_app()

if __name__ == "__main__":
    # Local development only. Use a production WSGI server for deployment.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
