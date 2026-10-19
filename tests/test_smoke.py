import os
import unittest
from datetime import date, timedelta

os.environ["SECRET_KEY"] = "test-secret-key-for-library-tests"
os.environ["DATABASE_URL"] = "sqlite://"

from backend.app import app
from backend.models import BookLoan, db


class LibrarySmokeTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {},
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _register(self, name, email, password="password-123"):
        return self.client.post("/api/auth/register", json={
            "name": name,
            "email": email,
            "password": password,
        })

    def test_first_account_is_admin_and_next_registration_is_student(self):
        first = self._register("Library Admin", "admin@example.test")
        second = self._register("A Student", "student@example.test")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json["user"]["role"], "admin")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json["user"]["role"], "student")

    def test_student_search_issue_return_and_late_fine(self):
        self._register("Library Admin", "admin@example.test")
        self.client.post("/api/auth/logout")
        self._register("A Student", "student@example.test")
        self.assertEqual(self.client.get("/api/books?q=python").json["books"], [])
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={
            "email": "admin@example.test",
            "password": "password-123",
        })
        book = self.client.post("/api/books", json={
            "title": "Python in Practice",
            "author": "Ada Author",
            "isbn": "9780000000001",
            "category": "Technology",
            "total_copies": 1,
        })
        self.assertEqual(book.status_code, 201)
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={
            "email": "student@example.test",
            "password": "password-123",
        })
        self.assertEqual(len(self.client.get("/api/books?q=python").json["books"]), 1)
        issue = self.client.post("/api/issues", json={"book_id": book.json["book"]["id"]})
        self.assertEqual(issue.status_code, 201)
        loan_id = issue.json["loan"]["id"]
        with self.app.app_context():
            loan = db.session.get(BookLoan, loan_id)
            loan.issued_at = date.today() - timedelta(days=15)
            loan.due_at = date.today() - timedelta(days=1)
            db.session.commit()
        returned = self.client.post(f"/api/issues/{loan_id}/return")
        self.assertEqual(returned.status_code, 200)
        self.assertEqual(returned.json["fine_amount"], "0.50")
        self.assertEqual(len(self.client.get("/api/fines").json["fines"]), 1)

    def test_app_pages_and_health_endpoints(self):
        home = self.client.get("/")
        dashboard = self.client.get("/dashboard")
        stylesheet = self.client.get("/static/css/style.css")
        script = self.client.get("/static/js/script.js")
        self.assertEqual(home.status_code, 200)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(script.status_code, 200)
        home.close()
        dashboard.close()
        stylesheet.close()
        script.close()
        self.assertEqual(self.client.get("/health").json["status"], "ok")
        self.assertEqual(self.client.get("/ready").json["status"], "ready")


if __name__ == "__main__":
    unittest.main()
