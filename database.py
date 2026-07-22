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

    # Household Members / People Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # Categories Table (for custom category creation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cat_type TEXT NOT NULL DEFAULT 'bill'
    )
    """)

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
        owner TEXT DEFAULT 'Shared / Household',
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
        owner TEXT DEFAULT 'Shared / Household',
        payment_method TEXT DEFAULT 'ACH / Checking',
        payment_detail TEXT DEFAULT '',
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
        next_paydate TEXT NOT NULL,
        owner TEXT DEFAULT 'Shared / Household'
    )
    """)

    # Bank Accounts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bank_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        bank_name TEXT NOT NULL,
        account_type TEXT DEFAULT 'Checking',
        account_number TEXT DEFAULT '',
        routing_number TEXT DEFAULT '',
        current_balance REAL DEFAULT 0.0,
        owner TEXT DEFAULT 'Shared / Household',
        notes TEXT
    )
    """)

    # Savings Buckets Table (with Parent Bank Account link)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS savings_buckets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        current_balance REAL NOT NULL DEFAULT 0.0,
        category TEXT NOT NULL DEFAULT 'General',
        icon TEXT DEFAULT ':material/savings:',
        owner TEXT DEFAULT 'Shared / Household',
        bank_account_id INTEGER DEFAULT NULL,
        bank_account_name TEXT DEFAULT ''
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
        reference_name TEXT,
        owner TEXT DEFAULT 'Shared / Household'
    )
    """)

    # --- Safe Migration logic for adding owner column if upgrading DB ---
    for table in ["cards", "bills", "income", "savings_buckets", "transactions", "bank_accounts"]:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cursor.fetchall()]
        if "owner" not in cols and table != "bank_accounts":
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN owner TEXT DEFAULT 'Shared / Household'")

    # Migration check for payment_method and payment_detail on bills
    cursor.execute("PRAGMA table_info(bills)")
    bill_cols = [c[1] for c in cursor.fetchall()]
    if "payment_method" not in bill_cols:
        cursor.execute("ALTER TABLE bills ADD COLUMN payment_method TEXT DEFAULT 'ACH / Checking'")
    if "payment_detail" not in bill_cols:
        cursor.execute("ALTER TABLE bills ADD COLUMN payment_detail TEXT DEFAULT ''")

    # Migration check for bank_account links on savings_buckets
    cursor.execute("PRAGMA table_info(savings_buckets)")
    bucket_cols = [c[1] for c in cursor.fetchall()]
    if "bank_account_name" not in bucket_cols:
        cursor.execute("ALTER TABLE savings_buckets ADD COLUMN bank_account_name TEXT DEFAULT ''")
    if "bank_account_id" not in bucket_cols:
        cursor.execute("ALTER TABLE savings_buckets ADD COLUMN bank_account_id INTEGER DEFAULT NULL")

    conn.commit()

    # Seed initial data if empty
    cursor.execute("SELECT COUNT(*) as count FROM people")
    if cursor.fetchone()["count"] == 0:
        seed_household_data(cursor)
        conn.commit()

    conn.close()

def seed_household_data(cursor):
    # People
    cursor.executemany("INSERT OR IGNORE INTO people (name) VALUES (?)", [
        ("Shared / Household",),
        ("Peter",),
        ("Partner",)
    ])

    # Default Bill Categories
    bill_cats = ["Housing", "Utilities", "Subscriptions", "Insurance", "Food & Groceries", "Debt", "Transportation", "Healthcare", "Entertainment", "General"]
    for c in bill_cats:
        cursor.execute("INSERT INTO categories (name, cat_type) VALUES (?, ?)", (c, "bill"))

    # Default Savings Categories
    savings_cats = ["Emergency", "Travel", "Auto", "Home", "Retirement", "Investments", "General"]
    for c in savings_cats:
        cursor.execute("INSERT INTO categories (name, cat_type) VALUES (?, ?)", (c, "savings"))

    # Sample Cards
    cursor.executemany("""
    INSERT INTO cards (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, owner)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Amex Gold", 1250.00, 10000.00, 24.99, 5, 25, 100.00, "Peter"),
        ("Chase Sapphire", 450.00, 8000.00, 21.49, 12, 2, 35.00, "Partner"),
        ("Shared Household Card", 890.00, 15000.00, 18.99, 1, 15, 50.00, "Shared / Household"),
    ])

    # Sample Bills
    cursor.executemany("""
    INSERT INTO bills (name, amount, due_day, frequency, category, auto_pay, is_active, owner, payment_method, payment_detail)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Rent / Mortgage", 1850.00, 1, "Monthly", "Housing", 1, 1, "Shared / Household", "ACH / Checking", "Primary Checking (...4012)"),
        ("Electric Utility", 120.00, 15, "Monthly", "Utilities", 1, 1, "Shared / Household", "ACH / Checking", "Primary Checking (...4012)"),
        ("Internet (Fiber)", 80.00, 10, "Monthly", "Utilities", 1, 1, "Peter", "Credit Card", "Amex Gold"),
        ("Car Insurance", 145.00, 20, "Monthly", "Insurance", 1, 1, "Partner", "Credit Card", "Chase Sapphire"),
        ("Cloud Server Hosting", 45.00, 5, "Monthly", "Subscriptions", 1, 1, "Peter", "Credit Card", "Amex Gold"),
    ])

    # Sample Income
    cursor.executemany("""
    INSERT INTO income (source, amount, frequency, next_paydate, owner)
    VALUES (?, ?, ?, ?, ?)
    """, [
        ("Peter Paycheck", 3200.00, "Bi-Weekly", date.today().isoformat(), "Peter"),
        ("Partner Salary", 2800.00, "Semi-Monthly", date.today().isoformat(), "Partner"),
    ])

    # Sample Bank Accounts
    cursor.executemany("""
    INSERT INTO bank_accounts (name, bank_name, account_type, account_number, routing_number, current_balance, owner)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Primary Checking", "Chase Bank", "Checking", "...4012", "021000021", 5200.00, "Shared / Household"),
        ("High-Yield Savings", "Capital One", "Savings", "...8821", "031100649", 12500.00, "Shared / Household"),
        ("Personal Checking", "Ally Bank", "Checking", "...1934", "071000013", 1850.00, "Peter"),
    ])

    # Sample Savings Buckets (Parent-Child linked to Bank Accounts)
    cursor.executemany("""
    INSERT INTO savings_buckets (name, target_amount, current_balance, category, icon, owner, bank_account_name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Emergency Reserve", 10000.00, 4500.00, "Emergency", ":material/shield:", "Shared / Household", "High-Yield Savings"),
        ("Vacation Fund", 3000.00, 1200.00, "Travel", ":material/flight_takeoff:", "Shared / Household", "High-Yield Savings"),
        ("Car Repair / Maintenance", 2000.00, 850.00, "Auto", ":material/build:", "Peter", "Personal Checking"),
    ])

    # Sample Transactions
    cursor.execute("""
    INSERT INTO transactions (created_at, type, amount, description, reference_name, owner)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M"), "Income", 3200.00, "Initial Paycheck Deposit", "Peter Paycheck", "Peter"))

# --- Query Helper Functions ---

def fetch_all(table):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def fetch_people():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM people ORDER BY id ASC")
    people = [r["name"] for r in cursor.fetchall()]
    conn.close()
    if "Shared / Household" not in people:
        people.insert(0, "Shared / Household")
    return people

def add_person(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (name.strip(),))
    conn.commit()
    conn.close()

def fetch_categories(cat_type="bill"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories WHERE cat_type=? ORDER BY name ASC", (cat_type,))
    cats = [r["name"] for r in cursor.fetchall()]
    conn.close()
    return cats

def add_category(name, cat_type="bill"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, cat_type) VALUES (?, ?)", (name.strip(), cat_type))
    conn.commit()
    conn.close()

def add_card(name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, owner="Shared / Household", notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO cards (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, owner, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, owner, notes))
    conn.commit()
    conn.close()

def update_card(card_id, name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, owner="Shared / Household", notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE cards SET name=?, balance=?, limit_amount=?, apr=?, statement_day=?, due_day=?, minimum_payment=?, owner=?, notes=?
    WHERE id=?
    """, (name, balance, limit_amount, apr, statement_day, due_day, minimum_payment, owner, notes, card_id))
    conn.commit()
    conn.close()

def delete_record(table, record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
    conn.commit()
    conn.close()

def add_bill(name, amount, due_day, frequency, category, auto_pay, owner="Shared / Household", payment_method="ACH / Checking", payment_detail="", is_active=1, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO bills (name, amount, due_day, frequency, category, auto_pay, owner, payment_method, payment_detail, is_active, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, amount, due_day, frequency, category, auto_pay, owner, payment_method, payment_detail, is_active, notes))
    conn.commit()
    conn.close()

def update_bill(bill_id, name, amount, due_day, frequency, category, auto_pay, owner="Shared / Household", payment_method="ACH / Checking", payment_detail="", is_active=1, notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE bills SET name=?, amount=?, due_day=?, frequency=?, category=?, auto_pay=?, owner=?, payment_method=?, payment_detail=?, is_active=?, notes=?
    WHERE id=?
    """, (name, amount, due_day, frequency, category, auto_pay, owner, payment_method, payment_detail, is_active, notes, bill_id))
    conn.commit()
    conn.close()

def add_income(source, amount, frequency, next_paydate, owner="Shared / Household"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO income (source, amount, frequency, next_paydate, owner)
    VALUES (?, ?, ?, ?, ?)
    """, (source, amount, frequency, next_paydate, owner))
    conn.commit()
    conn.close()

def update_income(income_id, source, amount, frequency, next_paydate, owner="Shared / Household"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE income SET source=?, amount=?, frequency=?, next_paydate=?, owner=?
    WHERE id=?
    """, (source, amount, frequency, next_paydate, owner, income_id))
    conn.commit()
    conn.close()

def add_bank_account(name, bank_name, account_type, account_number, routing_number, current_balance, owner="Shared / Household", notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO bank_accounts (name, bank_name, account_type, account_number, routing_number, current_balance, owner, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, bank_name, account_type, account_number, routing_number, current_balance, owner, notes))
    conn.commit()
    conn.close()

def update_bank_account(account_id, name, bank_name, account_type, account_number, routing_number, current_balance, owner="Shared / Household", notes=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE bank_accounts SET name=?, bank_name=?, account_type=?, account_number=?, routing_number=?, current_balance=?, owner=?, notes=?
    WHERE id=?
    """, (name, bank_name, account_type, account_number, routing_number, current_balance, owner, notes, account_id))
    conn.commit()
    conn.close()

def add_savings_bucket(name, target_amount, current_balance, category, owner="Shared / Household", icon=":material/savings:", bank_account_name=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO savings_buckets (name, target_amount, current_balance, category, owner, icon, bank_account_name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, target_amount, current_balance, category, owner, icon, bank_account_name))
    conn.commit()
    conn.close()

def update_savings_bucket(bucket_id, name, target_amount, current_balance, category, owner="Shared / Household", icon=":material/savings:", bank_account_name=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE savings_buckets SET name=?, target_amount=?, current_balance=?, category=?, owner=?, icon=?, bank_account_name=?
    WHERE id=?
    """, (name, target_amount, current_balance, category, owner, icon, bank_account_name, bucket_id))
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

def log_transaction(trans_type, amount, description, reference_name="", owner="Shared / Household"):
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
    INSERT INTO transactions (created_at, type, amount, description, reference_name, owner)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (created_at, trans_type, amount, description, reference_name, owner))
    conn.commit()
    conn.close()
