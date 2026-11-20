import json
import os
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request

ip_bp = Blueprint("ip_lab", __name__, template_folder="templates")
LOG_FILE = "target_ip_logs.json"
CONFIG_FILE = "target_ip_config.json"

# デフォルトの監視対象IPリスト
DEFAULT_TARGET_IPS = ["192.168.6.14"]


def load_target_ips():
  """監視対象のIPリストをファイルから読み込む"""
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      pass
  return DEFAULT_TARGET_IPS


def save_target_ips(ips):
  """監視対象のIPリストをファイルに保存する"""
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(ips, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def log_access(response):
  """アクセス監査ミドルウェア：指定されたIPからのアクセスのみを記録"""
  if "/static/" in request.path:
    return response

  client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
  target_ips = load_target_ips()

  # 監視対象のIPアドレスからのアクセスである場合のみ記録
  if client_ip in target_ips:
    # POSTデータやクエリパラメータの安全な取得
    body_data = None
    if request.method in ["POST", "PUT"]:
      try:
        body_data = request.get_json(silent=True) or request.form.to_dict()
      except Exception:
        body_data = "Could not parse body"

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ip": client_ip,
        "method": request.method,
        "path": request.path,
        "query": request.args.to_dict(),
        "body": body_data,
        "user_agent": request.headers.get("User-Agent", "Unknown"),
    }

    logs = []
    if os.path.exists(LOG_FILE):
      try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
          logs = json.load(f)
      except Exception:
        logs = []

    logs.insert(0, entry)
    logs = logs[:100]  # 最新100件保持

    try:
      with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
      pass

  return response


@ip_bp.route("/")
def index():
  return render_template("ip_logs.html")


# 📋 ログ取得API
@ip_bp.route("/api/ip/logs", methods=["GET"])
def get_logs():
  logs = []
  if os.path.exists(LOG_FILE):
    try:
      with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)
    except Exception:
      logs = []
  return jsonify(logs)


# 🗑️ ログクリアAPI
@ip_bp.route("/api/ip/clear", methods=["POST"])
def clear_logs():
  try:
    if os.path.exists(LOG_FILE):
      os.remove(LOG_FILE)
    return jsonify({"status": "success", "message": "監視ログをクリアしました"})
  except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500


# 🎯 現在の監視対象IP一覧を取得
@ip_bp.route("/api/ip/targets", methods=["GET"])
def get_targets():
  return jsonify(load_target_ips())


# ➕ 監視対象IPを追加
@ip_bp.route("/api/ip/targets", methods=["POST"])
def add_target():
  data = request.get_json() or {}
  new_ip = data.get("ip", "").strip()
  if not new_ip:
    return jsonify({"status": "error", "message": "IPアドレスが空です"}), 400

  ips = load_target_ips()
  if new_ip not in ips:
    ips.append(new_ip)
    save_target_ips(ips)

  return jsonify(
      {"status": "success", "targets": ips, "message": f"IP {new_ip} を追加しました"}
  )


# ➖ 監視対象IPを削除
@ip_bp.route("/api/ip/targets", methods=["DELETE"])
def remove_target():
  data = request.get_json() or {}
  target_ip = data.get("ip", "").strip()

  ips = load_target_ips()
  if target_ip in ips:
    ips.remove(target_ip)
    save_target_ips(ips)

  return jsonify(
      {
          "status": "success",
          "targets": ips,
          "message": f"IP {target_ip} を削除しました",
      }
  )