import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, jsonify, render_template, request

c2_bp = Blueprint("c2_lab", __name__, template_folder="templates")

BASE_DIR = Path(__file__).resolve().parent
SANDBOX_DIR = BASE_DIR / "sandbox"
KEY_FILE = BASE_DIR / "secret.key"
MAX_RESULTS = 100

ALLOWED_COMMANDS = {
    "AUDIT_SYS": "システム・権限情報の監査",
    "procs": "プロセス一覧取得 (ps aux)",
    "ps aux": "プロセス一覧取得 (ps aux)",
    "GET_PROCS": "プロセス一覧取得 (ps aux)",
    "AUTO_LOGS": "ディスク・ネットワーク状態の一括確認",
    "lock_files": "サンドボックス内ファイルの暗号化ロック",
    "unlock_files": "サンドボックス内ファイルの復号復元",
}


def load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


agent_key = load_or_create_key()
fernet = Fernet(agent_key)


def create_test_file() -> None:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SANDBOX_DIR / "secret.txt"
    if not file_path.exists():
        file_path.write_text(
            "これは企業の機密データベース、および重要財務ファイルを含む機密データです。",
            encoding="utf-8",
        )


def lock_sandbox_files(target_fernet: Fernet) -> int:
    create_test_file()
    count = 0
    for root, _, files in os.walk(SANDBOX_DIR):
        for file in files:
            if file.endswith(".locked") or file == KEY_FILE.name:
                continue
            file_path = Path(root) / file
            if file_path.resolve() == KEY_FILE.resolve():
                continue
            content = file_path.read_bytes()
            encrypted_content = target_fernet.encrypt(content)
            (Path(f"{file_path}.locked")).write_bytes(encrypted_content)
            file_path.unlink()
            count += 1
    return count


def unlock_sandbox_files(target_fernet: Fernet) -> tuple[int, list[str]]:
    if not SANDBOX_DIR.exists():
        return 0, []
    restored = 0
    errors: list[str] = []
    for root, _, files in os.walk(SANDBOX_DIR):
        for file in files:
            if not file.endswith(".locked"):
                continue
            locked_path = Path(root) / file
            original_path = Path(str(locked_path)[:-7])  # ".locked" (7文字) を除去
            try:
                decrypted = target_fernet.decrypt(locked_path.read_bytes())
                original_path.write_bytes(decrypted)
                locked_path.unlink()
                restored += 1
            except InvalidToken:
                errors.append(f"{file}: 鍵が一致しません")
            except Exception as e:
                errors.append(f"{file}: {e}")
    return restored, errors


create_test_file()

ACTIVE_AGENTS = {
    "target_node_web": {
        "ip": "192.168.111.129 (Sandbox)",
        "status": "Active",
    }
}
COMMAND_RESULTS: list[dict] = []


def record_result(command: str, output: str) -> None:
    COMMAND_RESULTS.insert(
        0,
        {
            "agent_id": "target_node_web",
            "command": command,
            "output": output,
        },
    )
    if len(COMMAND_RESULTS) > MAX_RESULTS:
        del COMMAND_RESULTS[MAX_RESULTS:]


@c2_bp.route("/")
def index():
    files = sorted(os.listdir(SANDBOX_DIR)) if SANDBOX_DIR.exists() else []
    return render_template("C2.html", files=files, sandbox=str(SANDBOX_DIR))


@c2_bp.route("/api/agents", methods=["GET"])
def get_agents():
    return jsonify(ACTIVE_AGENTS)


@c2_bp.route("/api/results", methods=["GET"])
def get_results():
    return jsonify(COMMAND_RESULTS)


@c2_bp.route("/api/c2/send_command", methods=["POST"])
def send_command():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    command = str(data.get("command", "")).strip()
    if not command:
        return jsonify({"error": "コマンドが空です"}), 400

    if command not in ALLOWED_COMMANDS:
        return jsonify({
            "error": "許可されていないコマンドです",
            "allowed_commands": sorted(ALLOWED_COMMANDS.keys()),
        }), 400

    try:
        if command == "AUDIT_SYS":
            is_root = (os.geteuid() == 0) if hasattr(os, "geteuid") else False
            info = {
                "system": platform.system(),
                "release": platform.release(),
                "node": platform.node(),
                "current_user": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
                "is_elevated_root": is_root,
                "working_directory": str(BASE_DIR),
            }
            output = json.dumps(info, ensure_ascii=False, indent=2)

        elif command in ("procs", "ps aux", "GET_PROCS"):
            if shutil.which("ps"):
                res = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
                output = res.stdout or "(出力なし)"
            else:
                output = "ps コマンドが利用できない環境です。"

        elif command == "AUTO_LOGS":
            if platform.system() == "Windows":
                disk_info = "N/A (Windows)"
                net_info = subprocess.check_output(["netstat", "-an"], text=True, timeout=5)
            else:
                if shutil.which("df"):
                    disk_info = subprocess.check_output(["df", "-h"], text=True, timeout=5)
                else:
                    disk_info = "df コマンドが利用できません。"

                if shutil.which("ss"):
                    net_info = subprocess.check_output(["ss", "-tuln"], text=True, timeout=5)
                elif shutil.which("netstat"):
                    net_info = subprocess.check_output(["netstat", "-an"], text=True, timeout=5)
                else:
                    net_info = "ss / netstat コマンドが利用できません。"

            output = f"=== [DISK INFO] ===\n{disk_info.strip()}\n=== [NETWORK INFO] ===\n{net_info.strip()}"

        elif command == "lock_files":
            count = lock_sandbox_files(fernet)
            output = f"[!] 暗号化されました: {count} 個のファイルがロック(.locked)されました。"

        elif command == "unlock_files":
            restored, errors = unlock_sandbox_files(fernet)
            output = f"[+] 復元完了！ {restored} 個のファイルが元に戻りました。"
            if errors:
                output += "\n[!] 一部エラー:\n" + "\n".join(errors)

    except Exception as e:
        output = f"Execution Failed: {e}"

    record_result(command, output)
    return jsonify({"status": "success", "command": command, "output": output})


@c2_bp.route("/api/lock", methods=["POST"])
def api_lock():
    try:
        count = lock_sandbox_files(fernet)
        msg = f"[!] 暗号化されました: {count} 個のファイルがロック(.locked)されました。"
        record_result("lock_files (API)", msg)
        return jsonify({"status": "success", "count": count, "message": msg})
    except Exception as e:
        return jsonify({"status": "error", "message": f"暗号化に失敗しました: {e}"}), 500


@c2_bp.route("/api/unlock", methods=["POST"])
def api_unlock():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    key_in = str(data.get("key", "")).strip()
    user_key = load_or_create_key() if not key_in else key_in.encode("utf-8")

    try:
        user_fernet = Fernet(user_key)
    except Exception:
        return jsonify({"status": "error", "message": "無効な鍵の形式です。"}), 400

    restored, errors = unlock_sandbox_files(user_fernet)
    if errors and restored == 0:
        return jsonify({
            "status": "error",
            "message": "復号に失敗しました（鍵が一致しないかファイルが破損しています）。",
            "details": errors,
        }), 400

    msg = f"[+] 復元完了！ {restored} 個のファイルが元に戻りました。"
    if errors:
        msg += f"（一部失敗: {len(errors)}件）"
    record_result("unlock_files (API)", msg)
    return jsonify({
        "status": "success",
        "restored": restored,
        "errors": errors,
        "message": msg,
    })