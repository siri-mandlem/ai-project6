CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student'
        CHECK (role IN ('admin', 'student')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(160) NOT NULL,
    isbn VARCHAR(32) UNIQUE,
    category VARCHAR(100) NOT NULL DEFAULT 'General',
    total_copies INTEGER NOT NULL DEFAULT 1 CHECK (total_copies > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS book_loans (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    book_id BIGINT NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
    issued_at DATE NOT NULL DEFAULT CURRENT_DATE,
    due_at DATE NOT NULL,
    returned_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (due_at >= issued_at),
    CHECK (returned_at IS NULL OR returned_at >= issued_at)
);

CREATE INDEX IF NOT EXISTS ix_book_loans_user_active
    ON book_loans (user_id, returned_at);
CREATE INDEX IF NOT EXISTS ix_book_loans_book_active
    ON book_loans (book_id, returned_at);

CREATE TABLE IF NOT EXISTS fines (
    id BIGSERIAL PRIMARY KEY,
    loan_id BIGINT NOT NULL UNIQUE REFERENCES book_loans(id) ON DELETE RESTRICT,
    amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    days_overdue INTEGER NOT NULL CHECK (days_overdue > 0),
    paid BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
