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
                "【対象組織（演習デモ環境） 情報システム部・経営陣 殿】\n\n"
                "貴殿らが頼みとしていたWindowsサーバー・Active Directory基盤、YAMAHAルーター／スイッチによる社内LANと拠点間VPN、そしてAWS上のクラウド環境やスナップショット・バックアップは、我々の手によって完全に掌握され、粉砕・無効化された。もはや自力でネットワークとシステムを復元するなどという甘い幻想は今すぐ捨て去れ。\n\n"
                "我々はすでに、貴社が死守すべきだった全てのコアデータを安全な海外オフショアサーバーへ完全抽出（Exfiltration）している：\n"
                "・Windowsドメイン・ファイルサーバー配下の機密設計データ・顧客／取引先データベース\n"
                "・AWS S3バケット／RDSおよびIAM認証情報・アクセスキー・バックアップスナップショット一式\n"
                "・YAMAHAルーター（RTX等）のコンフィグ・VPN設定・社内LANルーティング／ネットワーク構成情報\n"
                "・財務諸表・銀行口座情報・人事／給与台帳およびインシデント対応記録\n\n"
                "【要求事項と猶予なき期限】\n"
                "画面上のカウントダウンタイマーがゼロを迎えた瞬間、あるいは無駄な通報や隠蔽工作を試みたその秒に、上記の全データがダークウェブの公開リークサイトおよび各種メディアに向けて一斉に一般公開される。\n\n"
                "オンプレのWindowsと社内LAN、さらにAWSクラウドまで同時に押さえられたまま信用は完全失墜し、事業停止と莫大な損害賠償によって組織は確実に破滅・消滅する。\n"
                "全てを失って社会的な死を迎えるか、あるいは我々の要求する暗号資産を受け入れて秘密裏に幕引きを図るか——賢明で迅速な決断を勧める。"
            ),
            "Nov 21, 2026",
            "sample1.png",
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