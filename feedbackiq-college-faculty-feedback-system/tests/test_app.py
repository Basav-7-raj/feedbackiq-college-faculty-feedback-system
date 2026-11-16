import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash
from app import create_app


class FeedbackIQTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.temp_dir.name, "test.sqlite3")
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "DATABASE": db_path,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            from flask import current_app
            import sqlite3
            db = sqlite3.connect(current_app.config["DATABASE"])
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("student_test", generate_password_hash("a-secure-test-password"), "student"),
            )
            faculty_user = db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("faculty_test", generate_password_hash("another-secure-password"), "faculty"),
            ).lastrowid
            db.execute(
                "INSERT INTO faculty (user_id, name, department) VALUES (?, ?, ?)",
                (faculty_user, "Test Faculty", "Computer Science"),
            )
            db.commit()
            db.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_login_rejects_wrong_password(self):
        response = self.client.post("/", data={
            "username": "student_test", "password": "wrong-password"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password", response.data)

    def test_student_can_login_and_submit_feedback(self):
        response = self.client.post("/", data={
            "username": "student_test", "password": "a-secure-test-password"
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/student", data={
            "faculty_id": "1", "rating": "5", "comments": "Clear explanations"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Feedback submitted successfully", response.data)

    def test_student_cannot_open_admin(self):
        self.client.post("/", data={
            "username": "student_test", "password": "a-secure-test-password"
        })
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 403)

    def test_feedback_rating_validation(self):
        self.client.post("/", data={
            "username": "student_test", "password": "a-secure-test-password"
        })
        response = self.client.post("/student", data={
            "faculty_id": "1", "rating": "9", "comments": "Invalid rating"
        }, follow_redirects=True)
        self.assertIn(b"Rating must be between 1 and 5", response.data)


if __name__ == "__main__":
    unittest.main()
