from flask import Blueprint, jsonify, render_template, request, redirect, url_for, abort
import sqlite3
import os

dark_logger_bp = Blueprint(
    'dark_logger',
    __name__,
    template_folder='templates',
    static_folder='static'
)

DB_PATH = 'portal.db'

def init_db():
    """ 起動時にSQLiteデータベースと、架空の学校・企業を含む詳細データを初期化する """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS victims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            industry TEXT NOT NULL,
            data_size TEXT NOT NULL,
            seconds_left INTEGER NOT NULL,
            file_tree TEXT NOT NULL
        )
    ''')
    
    # データが空の場合のみ、学校や企業を含む初期データを投入
    cursor.execute('SELECT COUNT(*) FROM victims')
    if cursor.fetchone()[0] == 0:
        initial_data = [
            ("私立アペックス科学技術専門学校", "Educational Institution", "420 GB", 86400, 
             "\\Students\\Enrolled_PII_Database_2026.sql\n\\HR\\Faculty_CVs_Certificates.pdf\n\\Finance\\Tuition_Ledger_And_Bank_Records.xlsx\n\\Exams\\Questions_And_Answers_Secret.docx"),
            ("ネオサイバーテック・ジャパン", "Cybersecurity & IT", "310 GB", 72000, 
             "\\Clients\\Vulnerability_Assessments_TopSecret.pdf\n\\SourceCode\\ZeroDay_Exploit_PoC.git\n\\HR\\Employee_SSN_DL_Scans.zip"),
            ("ゼニス・バイオロジカル・ラボ", "Biotech & Healthcare", "550 GB", 65000, 
             "\\Research\\Phase3_Clinical_Trial_Results.pdf\n\\Patents\\Gene_Editing_Blueprints.dwg\n\\Management\\Board_Meeting_Minutes_2025.docx"),
            ("オーロラ・フィナンシャル・グループ", "Financial & Banking", "680 GB", 43200, 
             "\\Accounts\\VIP_Client_Transactions_2026.csv\n\\Audits\\Internal_Risk_Assessment.xlsx\n\\Network\\ActiveDirectory_NTDS.dit"),
            ("タイタン・ヘビーインダストリーズ", "Defense & Heavy Industries", "890 GB", 30000, 
             "\\Blueprints\\Autonomous_Drone_Specs_v2.dwg\n\\Contracts\\Ministry_Of_Defense_Signed.pdf\n\\Staff\\Security_Clearance_List.sql"),
            ("サイバー・エージェンシー・ネクサス", "IT Services", "180 GB", 95000, "\\ServerBackups\\Config_Prod.bak\n\\Invoices\\Q1_Billing.xlsx"),
            ("メトロポリタン・リアルエステート", "Real Estate", "240 GB", 54000, "\\Leases\\Commercial_Contracts.pdf\n\\Tenants\\Database_PII.csv"),
            ("アトラス・ロジスティクス・グローバル", "Freight & Logistics", "310 GB", 61000, "\\Fleet\\GPS_Tracking_Logs.log\n\\Manifests\\Shipping_2026.pdf"),
            ("クォンタム・エネルギー・ソリューションズ", "Energy & Utilities", "490 GB", 28000, "\\Grid\\SCADA_Network_Topology.kml\n\\Configs\\PowerPlant_Auth.json"),
            ("フェニックス・エアロスペース", "Aviation & Transport", "760 GB", 19000, "\\Aerodynamics\\WindTunnel_Test_Data.bin\n\\Suppliers\\Engine_Parts_Pricing.xlsx"),
            ("ネクサス・ニューラル・ネットワークス", "Artificial Intelligence", "530 GB", 41000, "\\AI\\Core_LLM_Weights_Encrypted.bin\n\\TrainingData\\Annotated_PII.json"),
            ("ステラー・マリタイム・シッピング", "Heavy Industries", "210 GB", 82000, "\\Vessels\\Cargo_Manifests_Secret.csv\n\\Ports\\Berth_Schedules.pdf"),
            ("ブラックウッド・ケミカル・グローバル", "Chemical & Materials", "380 GB", 37000, "\\Formula\\Refining_Catalyst_Recipe.pdf\n\\Safety\\Spill_Incident_Reports.docx"),
            ("ハイペリオン・ロボティクス", "Robotics & Automation", "290 GB", 50000, "\\SourceCode\\Robot_Kinematics_Engine.git\n\\CAD\\Actuator_Blueprints.step"),
            ("オメガ・ファーマシューティカルズ", "Pharmaceuticals", "440 GB", 33000, "\\Formulations\\Drug_Compound_X.pdf\n\\ClinicalTrials\\Patient_Feedback_PII.csv")
        ]
        cursor.executemany('''
            INSERT INTO victims (name, industry, data_size, seconds_left, file_tree)
            VALUES (?, ?, ?, ?, ?)
        ''', initial_data)
        conn.commit()
    conn.close()

# アプリ起動時にデータベースを初期化
init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- 公開ポータル画面 (market.html) ---
@dark_logger_bp.route('/')
def index():
    return render_template('market.html')

# --- 非同期データ取得用 API ---
@dark_logger_bp.route('/api/victims')
def api_victims():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM victims')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# --- 管理画面 (Dashboard / Read) ---
@dark_logger_bp.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    victims = conn.execute('SELECT * FROM victims').fetchall()
    conn.close()
    return render_template('admin.html', victims=victims)

# --- 新規ターゲット追加 (Create) ---
@dark_logger_bp.route('/admin/add', methods=['POST'])
def admin_add():
    name = request.form.get('name')
    industry = request.form.get('industry')
    data_size = request.form.get('data_size')
    seconds_left = int(request.form.get('seconds_left', 86400))
    file_tree = request.form.get('file_tree')

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO victims (name, industry, data_size, seconds_left, file_tree)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, industry, data_size, seconds_left, file_tree))
    conn.commit()
    conn.close()
    return redirect(url_for('dark_logger.admin_dashboard'))

# --- ターゲット削除 (Delete) ---
@dark_logger_bp.route('/admin/delete/<int:victim_id>', methods=['POST'])
def admin_delete(victim_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM victims WHERE id = ?', (victim_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dark_logger.admin_dashboard'))