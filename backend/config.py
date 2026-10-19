import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///library.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    LOAN_PERIOD_DAYS = int(os.environ.get("LOAN_PERIOD_DAYS", "14"))
    FINE_PER_DAY = os.environ.get("FINE_PER_DAY", "0.50")
