"""
لایه دیتابیس - Supabase Postgres
همه‌ی جدول‌ها اینجا ساخته و مدیریت می‌شوند.
"""
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import config

_pool = None


def get_conn():
    return psycopg2.connect(config.DATABASE_URL)


@contextmanager
def cursor():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT now(),
            exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            direction TEXT NOT NULL,           -- BUY / SELL
            score NUMERIC NOT NULL,
            strength TEXT NOT NULL,            -- STRONG / NORMAL
            entry NUMERIC NOT NULL,
            stop_loss NUMERIC NOT NULL,
            tp1 NUMERIC,
            tp2 NUMERIC,
            tp3 NUMERIC,
            reasons JSONB,
            outcome TEXT,                      -- WIN / LOSS / NULL (تا مشخص شدن)
            outcome_note TEXT,
            telegram_message_id BIGINT
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS news_events (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            event_time TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS condition_stats (
            condition_name TEXT PRIMARY KEY,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            weight NUMERIC DEFAULT 10
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)


# ---------------- Signals ----------------

def save_signal(data: dict) -> int:
    with cursor() as cur:
        cur.execute("""
            INSERT INTO signals
            (exchange, symbol, timeframe, direction, score, strength,
             entry, stop_loss, tp1, tp2, tp3, reasons)
            VALUES (%(exchange)s, %(symbol)s, %(timeframe)s, %(direction)s, %(score)s,
                    %(strength)s, %(entry)s, %(stop_loss)s, %(tp1)s, %(tp2)s, %(tp3)s, %(reasons)s)
            RETURNING id;
        """, data)
        return cur.fetchone()["id"]


def set_telegram_message_id(signal_id: int, message_id: int):
    with cursor() as cur:
        cur.execute(
            "UPDATE signals SET telegram_message_id = %s WHERE id = %s",
            (message_id, signal_id),
        )


def set_outcome(signal_id: int, outcome: str, note: str = ""):
    with cursor() as cur:
        cur.execute(
            "UPDATE signals SET outcome = %s, outcome_note = %s WHERE id = %s",
            (outcome, note, signal_id),
        )


def get_signal(signal_id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM signals WHERE id = %s", (signal_id,))
        return cur.fetchone()


def get_last_signal_for(symbol: str, timeframe: str, exchange: str):
    with cursor() as cur:
        cur.execute("""
            SELECT * FROM signals
            WHERE symbol=%s AND timeframe=%s AND exchange=%s
            ORDER BY created_at DESC LIMIT 1
        """, (symbol, timeframe, exchange))
        return cur.fetchone()


def get_open_signals():
    """سیگنال‌هایی که هنوز نتیجه‌شون (WIN/LOSS) مشخص نشده."""
    with cursor() as cur:
        cur.execute("SELECT * FROM signals WHERE outcome IS NULL ORDER BY created_at ASC")
        return cur.fetchall()



def get_recent_losses_sum(days: int) -> int:
    """تعداد ضررهای ثبت‌شده در N روز اخیر (برای فیلتر ریسک روزانه/هفتگی)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as c FROM signals
            WHERE outcome = 'LOSS' AND created_at >= %s
        """, (since,))
        return cur.fetchone()["c"]


# ---------------- News ----------------

def add_news_event(name: str, event_time: datetime):
    with cursor() as cur:
        cur.execute(
            "INSERT INTO news_events (name, event_time) VALUES (%s, %s)",
            (name, event_time),
        )


def get_upcoming_news(hours: int = 48):
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=hours)
    with cursor() as cur:
        cur.execute("""
            SELECT * FROM news_events
            WHERE event_time BETWEEN %s AND %s
            ORDER BY event_time ASC
        """, (now, until))
        return cur.fetchall()


def is_news_blackout(buffer_minutes: int) -> tuple:
    """آیا الان توی بازه‌ی ممنوعیت خبری هستیم؟ -> (bool, event_name|None)"""
    now = datetime.now(timezone.utc)
    with cursor() as cur:
        cur.execute("""
            SELECT * FROM news_events
            WHERE event_time BETWEEN %s AND %s
            ORDER BY event_time ASC LIMIT 1
        """, (now - timedelta(minutes=buffer_minutes), now + timedelta(minutes=buffer_minutes)))
        row = cur.fetchone()
        if row:
            return True, row["name"]
        return False, None


# ---------------- Condition stats (یادگیری ساده) ----------------

def bump_condition_stat(condition_name: str, win: bool):
    with cursor() as cur:
        cur.execute("""
            INSERT INTO condition_stats (condition_name, wins, losses)
            VALUES (%s, %s, %s)
            ON CONFLICT (condition_name) DO UPDATE SET
                wins = condition_stats.wins + %s,
                losses = condition_stats.losses + %s
        """, (condition_name, 1 if win else 0, 0 if win else 1,
              1 if win else 0, 0 if win else 1))


def get_condition_stats():
    with cursor() as cur:
        cur.execute("SELECT * FROM condition_stats")
        return cur.fetchall()


# ---------------- Bot state (key/value ساده) ----------------

def set_state(key: str, value: str):
    with cursor() as cur:
        cur.execute("""
            INSERT INTO bot_state (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, value))


def get_state(key: str, default=None):
    with cursor() as cur:
        cur.execute("SELECT value FROM bot_state WHERE key=%s", (key,))
        row = cur.fetchone()
        return row["value"] if row else default
