import os
import sqlite3
from datetime import datetime, date

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "money_tracker.db")

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Credit Cards Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0.0,
        limit_amount REAL NOT NULL DEFAULT 0.0,
        apr REAL DEFAULT 0.0,
        statement_day INTEGER DEFAULT 1,
        due_day INTEGER DEFAULT 15,
        minimum_payment REAL DEFAULT 0.0,
        notes TEXT
    )
    """)

    # Bills & Subscriptions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        due_day INTEGER NOT NULL,
        frequency TEXT NOT NULL DEFAULT 'Monthly',
        category TEXT NOT NULL DEFAULT 'General',
        auto_pay INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        notes TEXT
    )
    """)

    # Income & Paydays Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        amount REAL NOT NULL,
        frequency TEXT NOT NULL DEFAULT 'Bi-Weekly',
        next_paydate TEXT NOT NULL
    )
    """)

    # Savings Buckets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS savings_buckets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        current_balance REAL NOT NULL DEFAULT 0.0,
        category TEXT NOT NULL DEFAULT 'General',
        icon TEXT DEFAULT ':material/savings:'
    )
    """)

    # Transactions & History Log Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT NOT NULL,
        reference_name TEXT
    )
    """)

    conn.commit()

    # Seed initial sample data if empty
    cursor.execute("SELECT COUNT(*) as count FROM bills")
    if cursor.fetchone()["count"] == 0:
        seed_data(cursor)
        conn.commit()

    conn.close()

def seed_data(cursor):
    # Sample Cards
    cursor.executemany("""
    INSERT INTO cards (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Amex Gold", 1250.00, 10000.00, 24.99, 5, 25, 100.00),
        ("Chase Sapphire", 450.00, 8000.00, 21.49, 12, 2, 35.00),
    ])

    # Sample Bills
    cursor.executemany("""
    INSERT INTO bills (name, amount, due_day, frequency, category, auto_pay, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Rent / Mortgage", 1850.00, 1, "Monthly", "Housing", 1, 1),
        ("Electric Utility", 120.00, 15, "Monthly", "Utilities", 1, 1),
        ("Internet (Fiber)", 80.00, 10, "Monthly", "Utilities", 1, 1),
        ("Car Insurance", 145.00, 20, "Monthly", "Insurance", 1, 1),
        ("Cloud Server Hosting", 45.00, 5, "Monthly", "Subscriptions", 1, 1),
    ])

    # Sample Income
    cursor.execute("""
    INSERT INTO income (source, amount, frequency, next_paydate)
    VALUES (?, ?, ?, ?)
    """, ("Primary Paycheck", 3200.00, "Bi-Weekly", date.today().isoformat()))

    # Sample Savings Buckets
    cursor.executemany("""
    INSERT INTO savings_buckets (name, target_amount, current_balance, category, icon)
    VALUES (?, ?, ?, ?, ?)
    """, [
        ("Emergency Reserve", 10000.00, 4500.00, "Emergency", ":material/shield:"),
        ("Vacation Fund", 3000.00, 1200.00, "Travel", ":material/flight_takeoff:"),
        ("Car Repair / Maintenance", 2000.00, 850.00, "Auto", ":material/build:"),
    ])

    # Sample Transactions
    cursor.execute("""
    INSERT INTO transactions (created_at, type, amount, description, reference_name)
    VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M"), "Income", 3200.00, "Initial Paycheck Deposit", "Primary Paycheck"))

# --- Helper Query Functions ---

def fetch_all(table):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def add_card(name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO cards (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, notes))
    conn.commit()
    conn.close()

def update_card(card_id, name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE cards SET name=?, balance=?, limit_amount=?, apr=?, statement_day=?, due_day=?, minimum_payment=?, notes=?
    WHERE id=?
    """, (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, notes, card_id))
    conn.commit()
    conn.close()

def delete_record(table, record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
    conn.commit()
    conn.close()

def add_bill(name, amount, due_day, frequency, category, auto_pay, is_active=1, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO bills (name, amount, due_day, frequency, category, auto_pay, is_active, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, amount, due_day, frequency, category, auto_pay, is_active, notes))
    conn.commit()
    conn.close()

def update_bill(bill_id, name, amount, due_day, frequency, category, auto_pay, is_active=1, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE bills SET name=?, amount=?, due_day=?, frequency=?, category=?, auto_pay=?, is_active=?, notes=?
    WHERE id=?
    """, (name, amount, due_day, frequency, category, auto_pay, is_active, notes, bill_id))
    conn.commit()
    conn.close()

def add_income(source, amount, frequency, next_paydate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO income (source, amount, frequency, next_paydate)
    VALUES (?, ?, ?, ?)
    """, (source, amount, frequency, next_paydate))
    conn.commit()
    conn.close()

def add_savings_bucket(name, target_amount, current_balance, category, icon=":material/savings:"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO savings_buckets (name, target_amount, current_balance, category, icon)
    VALUES (?, ?, ?, ?, ?)
    """, (name, target_amount, current_balance, category, icon))
    conn.commit()
    conn.close()

def update_savings_balance(bucket_id, delta_amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE savings_buckets SET current_balance = current_balance + ? WHERE id=?
    """, (delta_amount, bucket_id))
    conn.commit()
    conn.close()

def log_transaction(trans_type, amount, description, reference_name=""):
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
    INSERT INTO transactions (created_at, type, amount, description, reference_name)
    VALUES (?, ?, ?, ?, ?)
    """, (created_at, trans_type, amount, description, reference_name))
    conn.commit()
    conn.close()
