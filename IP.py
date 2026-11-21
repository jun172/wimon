import ipaddress
import json
import os
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request

ip_bp = Blueprint("ip_lab", __name__, template_folder="templates")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "target_ip_logs.json")

# リストではなく「現在指定されている単一の監視対象IP（未指定時は None）」
active_target_ip: str | None = None


def is_valid_ip(ip_str: str) -> bool:
  """IPv4 / IPv6 アドレスとして妥当か判定する"""
  try:
    ipaddress.ip_address(ip_str)
    return True
  except ValueError:
    return False


def get_client_ip() -> str:
  """リクエスト元のIPアドレスを取得する（プロキシ経由時は先頭IPを優先）"""
  xff = request.headers.get("X-Forwarded-For", "").strip()
  if xff:
    first_ip = xff.split(",")[0].strip()
    if first_ip:
      return first_ip
  return (request.remote_addr or "").strip()


def log_access(response):
  """アクセス監査ミドルウェア：入力された対象IPからのアクセスのみを記録"""
  if "/static/" in request.path:
    return response

  client_ip = get_client_ip()

  # リストではなく、現在設定されている単一の入力IPと一致する場合のみ記録
  if active_target_ip and client_ip == active_target_ip:
    body_data = None
    if request.method in ["POST", "PUT", "PATCH"]:
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
          loaded = json.load(f)
          if isinstance(loaded, list):
            logs = loaded
      except Exception:
        logs = []

    logs.insert(0, entry)
    logs = logs[:100]

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
  if os.path.exists(LOG_FILE):
    try:
      with open(LOG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
          return jsonify(data)
    except Exception:
      pass
  return jsonify([])


# 🗑️ ログクリアAPI
@ip_bp.route("/api/ip/clear", methods=["POST"])
def clear_logs():
  try:
    if os.path.exists(LOG_FILE):
      os.remove(LOG_FILE)
    return jsonify({"status": "success", "message": "監視ログをクリアしました"})
  except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500


# 🎯 現在の監視対象IP（単一または null）を取得
@ip_bp.route("/api/ip/targets", methods=["GET"])
def get_targets():
  return jsonify({"ip": active_target_ip})


# ✏️ 入力されたIPを監視対象としてセット（リストではなく上書き）
@ip_bp.route("/api/ip/targets", methods=["POST"])
def set_target():
  global active_target_ip
  data = request.get_json(silent=True) or {}
  new_ip = str(data.get("ip", "")).strip()
  if not new_ip:
    return jsonify({"status": "error", "message": "IPアドレスが空です"}), 400
  if not is_valid_ip(new_ip):
    return jsonify({"status": "error", "message": "有効なIPアドレス形式ではありません"}), 400

  active_target_ip = new_ip
  return jsonify({
      "status": "success",
      "ip": active_target_ip,
      "message": f"監視対象IPを {active_target_ip} に設定しました",
  })


# ✖ 監視対象IPを解除
@ip_bp.route("/api/ip/targets", methods=["DELETE"])
def clear_target():
  global active_target_ip
  active_target_ip = None
  return jsonify({
      "status": "success",
      "ip": None,
      "message": "監視対象IPを解除しました",
  })