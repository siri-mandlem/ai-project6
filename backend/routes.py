from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from backend.models import Book, BookLoan, Fine, User, db


api = Blueprint("api", __name__, url_prefix="/api")


def _body():
    return request.get_json(silent=True) or {}


def _current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def _require_user(admin=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            user = _current_user()
            if user is None:
                return jsonify({"error": "Please sign in to continue."}), 401
            if admin and user.role != "admin":
                return jsonify({"error": "Administrator access is required."}), 403
            return function(*args, **kwargs)
        return wrapped
    return decorate


def _user_json(user):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def _book_json(book):
    active_loans = db.session.scalar(
        select(func.count(BookLoan.id)).where(
            BookLoan.book_id == book.id,
            BookLoan.returned_at.is_(None),
        )
    ) or 0
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "total_copies": book.total_copies,
        "available_copies": max(0, book.total_copies - active_loans),
    }


def _loan_json(loan):
    today = date.today()
    overdue_days = max(0, ((loan.returned_at or today) - loan.due_at).days)
    fine_amount = (
        loan.fine.amount
        if loan.fine
        else (Decimal(str(current_app.config["FINE_PER_DAY"])) * overdue_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    return {
        "id": loan.id,
        "user_id": loan.user_id,
        "student_name": loan.user.name,
        "student_email": loan.user.email,
        "book_id": loan.book_id,
        "book_title": loan.book.title,
        "issued_at": loan.issued_at.isoformat(),
        "due_at": loan.due_at.isoformat(),
        "returned_at": loan.returned_at.isoformat() if loan.returned_at else None,
        "overdue_days": overdue_days,
        "fine_amount": f"{fine_amount:.2f}",
        "fine_paid": bool(loan.fine and loan.fine.paid),
    }


@api.post("/auth/register")
def register():
    data = _body()
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().casefold()
    password = data.get("password")
    if not name or len(name) > 120 or not email or len(email) > 255:
        return jsonify({"error": "Enter a name and a valid email address."}), 400
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters."}), 400
    if db.session.scalar(select(User.id).where(func.lower(User.email) == email)):
        return jsonify({"error": "An account already exists for this email."}), 409

    # Bootstrap the library administrator with the first account; all later signups are students.
    role = "admin" if db.session.scalar(select(func.count(User.id))) == 0 else "student"
    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "An account already exists for this email."}), 409
    session.clear()
    session["user_id"] = user.id
    return jsonify({"user": _user_json(user), "message": "Account created."}), 201


@api.post("/auth/login")
def login():
    data = _body()
    email = str(data.get("email") or "").strip().casefold()
    password = data.get("password")
    user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not isinstance(password, str) or not check_password_hash(
        user.password_hash, password
    ):
        return jsonify({"error": "Email or password is incorrect."}), 401
    session.clear()
    session["user_id"] = user.id
    return jsonify({"user": _user_json(user), "message": "Signed in."})


@api.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Signed out."})


@api.get("/auth/me")
@_require_user()
def me():
    return jsonify({"user": _user_json(_current_user())})


@api.get("/dashboard")
@_require_user()
def dashboard():
    user = _current_user()
    active_query = select(func.count(BookLoan.id)).where(BookLoan.returned_at.is_(None))
    fine_query = select(func.coalesce(func.sum(Fine.amount), 0)).where(Fine.paid.is_(False))
    if user.role != "admin":
        active_query = active_query.where(BookLoan.user_id == user.id)
        fine_query = fine_query.join(BookLoan).where(BookLoan.user_id == user.id)
    return jsonify({
        "book_count": db.session.scalar(select(func.count(Book.id))) or 0,
        "active_loans": db.session.scalar(active_query) or 0,
        "unpaid_fines": f"{db.session.scalar(fine_query) or Decimal('0.00'):.2f}",
        "fine_per_day": str(current_app.config["FINE_PER_DAY"]),
        "student_count": (
            db.session.scalar(select(func.count(User.id)).where(User.role == "student")) or 0
        ) if user.role == "admin" else None,
    })


@api.get("/books")
def list_books():
    query = str(request.args.get("q") or "").strip()
    statement = select(Book).order_by(Book.title, Book.author)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(
            Book.title.ilike(pattern),
            Book.author.ilike(pattern),
            Book.isbn.ilike(pattern),
            Book.category.ilike(pattern),
        ))
    return jsonify({"books": [_book_json(book) for book in db.session.scalars(statement)]})


@api.post("/books")
@_require_user(admin=True)
def add_book():
    data = _body()
    title = str(data.get("title") or "").strip()
    author = str(data.get("author") or "").strip()
    isbn = str(data.get("isbn") or "").strip() or None
    category = str(data.get("category") or "General").strip() or "General"
    try:
        copies = int(data.get("total_copies", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Number of copies must be a positive whole number."}), 400
    if not title or len(title) > 200 or not author or len(author) > 160:
        return jsonify({"error": "Book title and author are required."}), 400
    if len(category) > 100 or (isbn and len(isbn) > 32) or copies < 1 or copies > 10000:
        return jsonify({"error": "Check the category, ISBN, and copy count."}), 400
    book = Book(
        title=title,
        author=author,
        isbn=isbn,
        category=category,
        total_copies=copies,
    )
    db.session.add(book)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "That ISBN is already in the library."}), 409
    return jsonify({"book": _book_json(book)}), 201


@api.post("/issues")
@_require_user()
def issue_book():
    data = _body()
    user = _current_user()
    try:
        book_id = int(data.get("book_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Select a valid book."}), 400

    borrower = user
    borrower_email = str(data.get("student_email") or "").strip().casefold()
    if user.role == "admin" and borrower_email:
        borrower = db.session.scalar(
            select(User).where(func.lower(User.email) == borrower_email)
        )
        if borrower is None or borrower.role != "student":
            return jsonify({"error": "Select a registered student account."}), 404
    elif user.role != "admin" and borrower_email:
        return jsonify({"error": "Students can only issue books to themselves."}), 403

    book = db.session.get(Book, book_id)
    if book is None:
        return jsonify({"error": "Book not found."}), 404
    active_count = db.session.scalar(select(func.count(BookLoan.id)).where(
        BookLoan.book_id == book.id,
        BookLoan.returned_at.is_(None),
    )) or 0
    if active_count >= book.total_copies:
        return jsonify({"error": "No copies of this book are currently available."}), 409
    duplicate = db.session.scalar(select(BookLoan.id).where(
        BookLoan.user_id == borrower.id,
        BookLoan.book_id == book.id,
        BookLoan.returned_at.is_(None),
    ))
    if duplicate:
        return jsonify({"error": "This student already has an active loan for this book."}), 409
    try:
        loan_days = int(current_app.config["LOAN_PERIOD_DAYS"])
    except (TypeError, ValueError):
        return jsonify({"error": "The configured loan period is invalid."}), 500
    if loan_days < 1 or loan_days > 365:
        return jsonify({"error": "The configured loan period must be between 1 and 365 days."}), 500
    loan = BookLoan(
        user_id=borrower.id,
        book_id=book.id,
        issued_at=date.today(),
        due_at=date.today() + timedelta(days=loan_days),
    )
    db.session.add(loan)
    db.session.commit()
    return jsonify({"loan": _loan_json(loan)}), 201


@api.get("/issues")
@_require_user()
def list_issues():
    user = _current_user()
    statement = select(BookLoan).order_by(BookLoan.issued_at.desc(), BookLoan.id.desc())
    if user.role != "admin":
        statement = statement.where(BookLoan.user_id == user.id)
    status = request.args.get("status")
    if status == "active":
        statement = statement.where(BookLoan.returned_at.is_(None))
    elif status == "returned":
        statement = statement.where(BookLoan.returned_at.is_not(None))
    return jsonify({"issues": [_loan_json(loan) for loan in db.session.scalars(statement)]})


@api.post("/issues/<int:loan_id>/return")
@_require_user()
def return_book(loan_id):
    user = _current_user()
    loan = db.session.get(BookLoan, loan_id)
    if loan is None:
        return jsonify({"error": "Loan not found."}), 404
    if user.role != "admin" and loan.user_id != user.id:
        return jsonify({"error": "You can only return books issued to your account."}), 403
    if loan.returned_at:
        return jsonify({"error": "This book has already been returned."}), 409

    returned_at = date.today()
    overdue_days = max(0, (returned_at - loan.due_at).days)
    loan.returned_at = returned_at
    if overdue_days:
        try:
            fine_per_day = Decimal(str(current_app.config["FINE_PER_DAY"]))
            if not fine_per_day.is_finite() or fine_per_day <= 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            db.session.rollback()
            return jsonify({"error": "The configured daily fine must be a positive amount."}), 500
        amount = (fine_per_day * overdue_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        db.session.add(Fine(
            loan_id=loan.id,
            amount=amount,
            days_overdue=overdue_days,
        ))
    db.session.commit()
    return jsonify({
        "loan": _loan_json(loan),
        "message": "Book returned.",
        "fine_amount": f"{loan.fine.amount:.2f}" if loan.fine else "0.00",
    })


@api.get("/fines")
@_require_user()
def list_fines():
    user = _current_user()
    statement = select(Fine).join(BookLoan).order_by(Fine.created_at.desc(), Fine.id.desc())
    if user.role != "admin":
        statement = statement.where(BookLoan.user_id == user.id)
    fines = db.session.scalars(statement)
    return jsonify({"fines": [{
        "id": fine.id,
        "loan_id": fine.loan_id,
        "student_name": fine.loan.user.name,
        "student_email": fine.loan.user.email,
        "book_title": fine.loan.book.title,
        "amount": f"{fine.amount:.2f}",
        "days_overdue": fine.days_overdue,
        "paid": fine.paid,
        "created_at": fine.created_at.isoformat() if fine.created_at else None,
    } for fine in fines]})


@api.post("/fines/<int:fine_id>/pay")
@_require_user()
def pay_fine(fine_id):
    user = _current_user()
    fine = db.session.get(Fine, fine_id)
    if fine is None:
        return jsonify({"error": "Fine not found."}), 404
    if user.role != "admin" and fine.loan.user_id != user.id:
        return jsonify({"error": "You can only update fines on your account."}), 403
    if fine.paid:
        return jsonify({"error": "This fine is already marked as paid."}), 409
    fine.paid = True
    db.session.commit()
    return jsonify({"message": "Fine marked as paid."})
