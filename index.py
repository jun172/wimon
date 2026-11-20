from datetime import datetime
import sqlite3
from flask import Blueprint, jsonify, render_template

index_bp = Blueprint(
    'index_portal', __name__, template_folder='templates', static_folder='static'
)
DB_PATH = 'portal.db'
DEADLINE = datetime(2026, 11, 21, 12, 0, 0)


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  # 既存のテーブルを一度リセットして正しいスキーマで再構築する
  cursor.execute('DROP TABLE IF EXISTS victims')

  cursor.execute('''
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
            breach_date TEXT NOT NULL
        )
    ''')

  # 10個のプレースホルダー（?）に対応する10個の要素を持つタプルリスト
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
              "貴殿らが頼みとしていたオンプレミスサーバー、仮想インフラ、そして全てのオフサイト・物理バックアップは、我々の手によって完全に掌握され、粉砕・無効化された。もはや自力でシステムを復元するなどという甘い幻想は今すぐ捨て去れ。\n\n"
              "我々はすでに、貴校が死守すべきだった全てのコアデータを安全な海外オフショアサーバーへ完全抽出（Exfiltration）している：\n"
              "・在校生および卒業生全員の機密個人情報（PII）データベース\n"
              "・教職員の人事評価、給与台帳、極秘履歴書\n"
              "・数億円規模の銀行口座・財務諸表・学費振込履歴\n"
              "・次年度の極秘入試問題および全解答データ\n\n"
              "【要求事項と猶予なき期限】\n"
              "画面上のカウントダウンタイマーがゼロを迎えた瞬間、あるいは無駄な警察への通報や隠蔽工作を試みたその秒に、上記の全データがダークウェブの公開リークサイトおよび各種メディアに向けて一斉に一般公開される。\n\n"
              "教育機関としての社会的信用は完全失墜し、生徒たちの未来は閉ざされ、数億〜数十億円規模の損害賠償によって学校法人は確実に破滅・消滅する。\n"
              "全てを失って社会的な死を迎えるか、あるいは我々の要求する15億円相当の暗号資産を受け入れて秘密裏に幕引きを図るか——賢明で迅速な決断を勧める。"
          ),
          "Nov 16, 2026",
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
      ),
  ]

  # 10個のカラムに対する10個のプレースホルダー (?)
  cursor.executemany(
      """
        INSERT INTO victims (name, industry, data_size, encrypted_servers, ransom_amount, critical_level, seconds_left, file_tree, statement, breach_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


@index_bp.route('/')
def show_extortion_portal():
  conn = get_db_connection()
  victims_list = conn.execute('SELECT * FROM victims ORDER BY id ASC').fetchall()
  conn.close()

  if not victims_list:
    return 'Target data not found', 404

  now = datetime.now()
  remaining_seconds = int((DEADLINE - now).total_seconds())
  if remaining_seconds < 0:
    remaining_seconds = 0

  portal_dict = dict(victims_list[0])
  portal_dict['dynamic_seconds_left'] = remaining_seconds

  return render_template(
      'index.html',
      portal=portal_dict,
      victims=victims_list,
      targets=victims_list,
      dynamic_seconds_left=remaining_seconds,
  )

@index_bp.route('/target/<int:target_id>')
def switch_target(target_id):
  conn = get_db_connection()
  portal_data = conn.execute(
      'SELECT * FROM victims WHERE id = ?', (target_id,)
  ).fetchone()
  targets_list = conn.execute(
      'SELECT id, name, industry, data_size FROM victims'
  ).fetchall()
  conn.close()

  if not portal_data:
    return 'Target not found', 404

  now = datetime.now()
  remaining_seconds = int((DEADLINE - now).total_seconds())
  if remaining_seconds < 0:
    remaining_seconds = 0

  portal_dict = dict(portal_data)
  portal_dict['dynamic_seconds_left'] = remaining_seconds

  return render_template('index.html', portal=portal_dict, targets=targets_list)