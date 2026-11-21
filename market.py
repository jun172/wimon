from datetime import datetime
import sqlite3
from flask import Blueprint, render_template

market_bp = Blueprint(
    'market_portal', __name__, template_folder='templates', static_folder='static'
)

DB_PATH = 'portal.db'
DEADLINE = datetime(2026, 11, 21, 12, 0, 0)


def get_db_connection():
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn


@market_bp.route('/market')
def show_market_portal():
  conn = get_db_connection()
  victims_list = conn.execute('SELECT * FROM victims ORDER BY id ASC').fetchall()
  conn.close()

  now = datetime.now()
  remaining_seconds = max(0, int((DEADLINE - now).total_seconds()))

  return render_template(
      'market.html',
      victims=victims_list,
      dynamic_seconds_left=remaining_seconds,
  )