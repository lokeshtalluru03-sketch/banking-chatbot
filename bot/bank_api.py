"""
Mock "core banking system".

In production the chatbot never owns money data — it calls the bank's
internal APIs (core banking, card management, CRM). This class plays that
role using a local SQLite database so everything runs on your laptop.
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bank.db"

DEMO_CUSTOMERS = {
    # customer_id: (name, password)  -- demo only; real banks use OAuth/MFA
    "alex": ("Alex Morgan", "demo123"),
    "priya": ("Priya Shah", "demo123"),
}

MERCHANTS = [
    ("Grocery Mart", "Groceries"), ("Fuel Stop", "Transport"), ("Coffee House", "Dining"),
    ("StreamFlix", "Subscriptions"), ("City Power & Light", "Utilities"),
    ("Online Shop", "Shopping"), ("Pizza Corner", "Dining"), ("Pharmacy Plus", "Health"),
]


class BankAPI:
    def __init__(self, db_path=DB_PATH, reset=False):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if reset and db_path.exists():
            db_path.unlink()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._setup()

    # ---------- setup ----------
    def _setup(self):
        c = self.conn
        c.executescript("""
        CREATE TABLE IF NOT EXISTS accounts(
            customer_id TEXT, type TEXT, number TEXT, balance REAL,
            PRIMARY KEY(customer_id, type));
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, account TEXT,
            ts TEXT, description TEXT, category TEXT, amount REAL);
        CREATE TABLE IF NOT EXISTS cards(
            customer_id TEXT PRIMARY KEY, last4 TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS cases(
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, type TEXT,
            ts TEXT, details TEXT, status TEXT);
        """)
        if c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            self._seed()
        c.commit()

    def _seed(self):
        rng = random.Random(42)
        for cid in DEMO_CUSTOMERS:
            self.conn.execute("INSERT INTO accounts VALUES(?,?,?,?)",
                              (cid, "checking", f"{rng.randint(1000,9999)}", round(rng.uniform(1500, 6000), 2)))
            self.conn.execute("INSERT INTO accounts VALUES(?,?,?,?)",
                              (cid, "savings", f"{rng.randint(1000,9999)}", round(rng.uniform(5000, 25000), 2)))
            self.conn.execute("INSERT INTO cards VALUES(?,?,?)", (cid, f"{rng.randint(1000,9999)}", "active"))
            now = datetime.now()
            for i in range(15):
                merchant, cat = rng.choice(MERCHANTS)
                ts = (now - timedelta(days=i, hours=rng.randint(0, 12))).strftime("%Y-%m-%d %H:%M")
                self.conn.execute(
                    "INSERT INTO transactions(customer_id,account,ts,description,category,amount) VALUES(?,?,?,?,?,?)",
                    (cid, "checking", ts, merchant, cat, -round(rng.uniform(4, 180), 2)))
            self.conn.execute(
                "INSERT INTO transactions(customer_id,account,ts,description,category,amount) VALUES(?,?,?,?,?,?)",
                (cid, "checking", (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), "Payroll Deposit", "Income", 2850.00))

    # ---------- auth ----------
    @staticmethod
    def authenticate(customer_id: str, password: str):
        rec = DEMO_CUSTOMERS.get(customer_id.lower().strip())
        if rec and rec[1] == password:
            return rec[0]
        return None

    # ---------- reads ----------
    def get_balances(self, cid):
        rows = self.conn.execute("SELECT type, number, balance FROM accounts WHERE customer_id=?", (cid,)).fetchall()
        return {r["type"]: {"number": r["number"], "balance": r["balance"]} for r in rows}

    def get_transactions(self, cid, limit=5):
        rows = self.conn.execute(
            "SELECT ts, description, category, amount, account FROM transactions "
            "WHERE customer_id=? ORDER BY ts DESC LIMIT ?", (cid, limit)).fetchall()
        return [dict(r) for r in rows]

    def spending_by_category(self, cid, days=30):
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT category, -SUM(amount) AS spent FROM transactions "
            "WHERE customer_id=? AND amount<0 AND ts>=? GROUP BY category ORDER BY spent DESC",
            (cid, since)).fetchall()
        return {r["category"]: round(r["spent"], 2) for r in rows}

    def get_card(self, cid):
        r = self.conn.execute("SELECT last4, status FROM cards WHERE customer_id=?", (cid,)).fetchone()
        return dict(r) if r else None

    # ---------- writes ----------
    def transfer(self, cid, from_acct, to_acct, amount):
        if from_acct == to_acct:
            return False, "The 'from' and 'to' accounts must be different."
        if amount <= 0:
            return False, "Amount must be greater than zero."
        if amount > 10000:
            return False, "Chat transfers are limited to $10,000. Please visit online banking or a branch for larger amounts."
        bal = self.get_balances(cid)
        if bal[from_acct]["balance"] < amount:
            return False, f"Insufficient funds: your {from_acct} balance is ${bal[from_acct]['balance']:,.2f}."
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.conn:
            self.conn.execute("UPDATE accounts SET balance=balance-? WHERE customer_id=? AND type=?", (amount, cid, from_acct))
            self.conn.execute("UPDATE accounts SET balance=balance+? WHERE customer_id=? AND type=?", (amount, cid, to_acct))
            self.conn.execute(
                "INSERT INTO transactions(customer_id,account,ts,description,category,amount) VALUES(?,?,?,?,?,?)",
                (cid, from_acct, ts, f"Transfer to {to_acct}", "Transfer", -amount))
            self.conn.execute(
                "INSERT INTO transactions(customer_id,account,ts,description,category,amount) VALUES(?,?,?,?,?,?)",
                (cid, to_acct, ts, f"Transfer from {from_acct}", "Transfer", amount))
        ref = f"TRF{random.randint(100000, 999999)}"
        return True, ref

    def block_card(self, cid):
        with self.conn:
            self.conn.execute("UPDATE cards SET status='blocked' WHERE customer_id=?", (cid,))
        return self.open_case(cid, "card_block", "Card blocked via chatbot; replacement requested")

    def open_case(self, cid, case_type, details):
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO cases(customer_id,type,ts,details,status) VALUES(?,?,?,?,?)",
                (cid, case_type, datetime.now().strftime("%Y-%m-%d %H:%M"), details, "open"))
        return f"CASE-{cur.lastrowid:05d}"


BRANCH_INFO = (
    "🏦 **Branch hours:** Mon–Fri 9:00 AM–5:00 PM, Sat 9:00 AM–12:00 PM, closed Sunday.\n\n"
    "🏧 ATMs are available 24/7. Use the branch locator in the mobile app to find the nearest one."
)

LOAN_INFO = (
    "Here are our current *sample* rates (demo data):\n\n"
    "| Loan type | APR from | Term |\n|---|---|---|\n"
    "| Personal loan | 8.99% | 1–5 yrs |\n"
    "| Auto loan | 6.49% | 3–7 yrs |\n"
    "| 30-yr fixed mortgage | 6.75% | 30 yrs |\n\n"
    "Rates depend on credit history. Want me to connect you with a loan officer?"
)
