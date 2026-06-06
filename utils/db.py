"""
매매 기록 DB (SQLite)
"""
import sqlite3
import datetime
import os
from config.settings import DB_PATH

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


class TradeDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT    NOT NULL,
                code       TEXT    NOT NULL,
                name       TEXT,
                side       TEXT    NOT NULL,  -- BUY / SELL
                qty        INTEGER NOT NULL,
                price      INTEGER NOT NULL,
                is_simul   INTEGER NOT NULL,
                reason     TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                date        TEXT PRIMARY KEY,
                total_eval  INTEGER,
                profit_rate REAL,
                available   INTEGER
            )
        """)
        self.conn.commit()

    def save_order(self, code, name, side, qty, price, is_simul, reason=""):
        self.conn.execute(
            "INSERT INTO orders (timestamp, code, name, side, qty, price, is_simul, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.datetime.now().isoformat(), code, name, side,
             qty, price, int(is_simul), reason)
        )
        self.conn.commit()

    def save_daily_summary(self, total_eval, profit_rate, available):
        date = datetime.date.today().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO daily_summary VALUES (?, ?, ?, ?)",
            (date, total_eval, profit_rate, available)
        )
        self.conn.commit()

    def get_today_orders(self):
        today = datetime.date.today().isoformat()
        cur = self.conn.execute(
            "SELECT * FROM orders WHERE timestamp LIKE ?", (f"{today}%",)
        )
        return cur.fetchall()
