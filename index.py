from datetime import datetime
from pathlib import Path
import sqlite3
from flask import Blueprint, render_template

index_bp = Blueprint(
    "index_portal",
    __name__,
    template_folder="templates",
    static_folder="static",
)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portal.db"
DEADLINE = datetime(2026, 11, 21, 12, 0, 0)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 既存のテーブルを一度リセットして正しいスキーマで再構築する
    cursor.execute("DROP TABLE IF EXISTS victims")

    cursor.execute("""
        CREATE TABLE victims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            industry TEXT NOT NULL,
            data_size TEXT NOT NULL,
            encrypted_servers TEXT NOT NULL,
            ransom_amount TEXT NOT NULL,
            critical_level TEXT NOT NULL,
            seconds_left INTEGER NOT NULL,
            file_tree TEXT NOT NULL,
            statement TEXT NOT NULL,
            breach_date TEXT NOT NULL,
            image_filename TEXT
        )
    """)

    # 11個のカラム（image_filename を追加）に対応する11個の要素を持つタプルリスト
    initial_data = [
        (
            "神戸電子専門学校",
            "Educational Institution",
            "420.5 GB",
            "128 / 128",
            "¥1,500,000,000",
            "CRITICAL (Level 5)",
            86400,
            (
                "\\Students\\Enrolled_PII_Database_2026.sql\n"
                "\\HR\\Faculty_CVs.pdf\n"
                "\\Finance\\Bank_Records.xlsx\n"
                "\\Exams\\Secret_Questions.docx"
            ),
            (
                "【神戸電子専門学校 経営陣・理事会 殿】\n\n"
            ),
            "Nov 16, 2026",
            "sample1.png",  # static/images/ に置くファイル名を指定（不要なら "" にする）
        ),
        (
            "ネオサイバーテック・ジャパン",
            "Cybersecurity & IT",
            "310.0 GB",
            "64 / 64",
            "¥800,000,000",
            "HIGH (Level 4)",
            72000,
            (
                "\\Clients\\Vulnerability_Assessments.pdf\n"
                "\\SourceCode\\ZeroDay_PoC.git"
            ),
            (
                "【セキュリティ企業の完全陥落に関する最終通告】\n\n"
                "セキュリティを謳う貴社のインフラが最も脆弱であったことは皮肉極まりない。すべての資産、ソースコード、および顧客の脆弱性診断データは我々の手に落ちた。\n\n"
                "猶予はない。要求された身代金を速やかに支払わない限り、未公開のゼロデイエクスプロイトおよび全クライアントリストを全世界へ暴露する。"
            ),
            "Nov 17, 2026",
            "",
        ),
    ]

    # 11個のカラムに対する11個のプレースホルダー (?)
    cursor.executemany(
        """
        INSERT INTO victims (
            name, industry, data_size, encrypted_servers, ransom_amount,
            critical_level, seconds_left, file_tree, statement, breach_date, image_filename
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        initial_data,
    )
    conn.commit()
    conn.close()


# 起動時に実行
init_db()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@index_bp.route("/")
def show_extortion_portal():
    conn = get_db_connection()
    victims_list = conn.execute("SELECT * FROM victims ORDER BY id ASC").fetchall()
    conn.close()

    if not victims_list:
        return "Target data not found", 404

    now = datetime.now()
    remaining_seconds = max(0, int((DEADLINE - now).total_seconds()))

    portal_dict = dict(victims_list[0])
    portal_dict["image_filename"] = portal_dict.get("image_filename") or ""
    portal_dict["dynamic_seconds_left"] = remaining_seconds

    return render_template(
        "index.html",
        portal=portal_dict,
        victims=victims_list,
        targets=victims_list,
        dynamic_seconds_left=remaining_seconds,
    )


@index_bp.route("/target/<int:target_id>")
def switch_target(target_id):
    conn = get_db_connection()
    portal_data = conn.execute(
        "SELECT * FROM victims WHERE id = ?", (target_id,)
    ).fetchone()
    targets_list = conn.execute(
        "SELECT id, name, industry, data_size FROM victims"
    ).fetchall()
    conn.close()

    if not portal_data:
        return "Target not found", 404

    now = datetime.now()
    remaining_seconds = max(0, int((DEADLINE - now).total_seconds()))

    portal_dict = dict(portal_data)
    portal_dict["image_filename"] = portal_dict.get("image_filename") or ""
    portal_dict["dynamic_seconds_left"] = remaining_seconds

    return render_template("index.html", portal=portal_dict, targets=targets_list)