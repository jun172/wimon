from datetime import datetime
from pathlib import Path
import sqlite3
from flask import Blueprint, render_template

market_bp = Blueprint(
    "market_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portal.db"
DEADLINE = datetime(2026, 11, 21, 12, 0, 0)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@market_bp.route("/")
def show_market_portal():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM victims ORDER BY id ASC").fetchall()
    finally:
        conn.close()

    victims_list = []
    for row in rows:
        item = dict(row)
        item["image_filename"] = item.get("image_filename") or ""
        victims_list.append(item)

    now = datetime.now()
    remaining_seconds = max(0, int((DEADLINE - now).total_seconds()))

    return render_template(
        "market.html",
        victims=victims_list,
        dynamic_seconds_left=remaining_seconds,
    )