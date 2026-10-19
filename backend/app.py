from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.config import Config
from backend.models import db
from backend.routes import api


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path="/static",
)
app.config.from_object(Config)
if not app.config.get("SECRET_KEY"):
    raise RuntimeError("Set SECRET_KEY to a strong, unique value before starting the app.")
database_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
if database_url.startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://" + database_url[len("postgres://"):]

db.init_app(app)
app.register_blueprint(api)


@app.get("/")
@app.get("/dashboard")
@app.get("/addbook")
@app.get("/issuebook")
@app.get("/returnbook")
@app.get("/issuedbooks")
@app.get("/searchbooks")
@app.get("/finecalculation")
@app.get("/login")
@app.get("/register")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Database readiness check failed")
        return jsonify({"status": "not_ready"}), 503
    return jsonify({"status": "ready"})


with app.app_context():
    db.create_all()
