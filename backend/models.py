from datetime import date, datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    loans = db.relationship("BookLoan", back_populates="user")


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(160), nullable=False, index=True)
    isbn = db.Column(db.String(32), unique=True, nullable=True)
    category = db.Column(db.String(100), nullable=False, default="General")
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    loans = db.relationship("BookLoan", back_populates="book")


class BookLoan(db.Model):
    __tablename__ = "book_loans"
    __table_args__ = (
        db.CheckConstraint("due_at >= issued_at", name="ck_book_loans_due_after_issue"),
        db.CheckConstraint(
            "returned_at IS NULL OR returned_at >= issued_at",
            name="ck_book_loans_return_after_issue",
        ),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    user_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    book_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey("books.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issued_at = db.Column(db.Date, nullable=False, default=date.today)
    due_at = db.Column(db.Date, nullable=False)
    returned_at = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="loans")
    book = db.relationship("Book", back_populates="loans")
    fine = db.relationship("Fine", back_populates="loan", uselist=False)


class Fine(db.Model):
    __tablename__ = "fines"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True)
    loan_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey("book_loans.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    days_overdue = db.Column(db.Integer, nullable=False)
    paid = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    loan = db.relationship("BookLoan", back_populates="fine")

    def amount_as_decimal(self):
        return Decimal(self.amount)
