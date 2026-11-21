import re
import shutil
import subprocess
from flask import Blueprint, jsonify, render_template, request

# Blueprintの定義（url_prefix="/nmap" で登録する場合はそのまま、未指定登録ならアプリ側で指定）
namp = Blueprint("nmap", __name__, template_folder="templates")

TARGET_IP = "192.168.111.129"

# 許可するスキャンオプション
ALLOWED_SCAN_TYPES = {
    "-sT": "TCP Connect スキャン (一般権限OK/安全)",
    "-sV": "サービス・バージョン検出 (一般権限OK)",
    "-sn": "Ping スキャン / ホスト発見 (一般権限OK)",
}

# 許可するNSEスクリプト
ALLOWED_SCRIPTS = {
    "none": "スクリプトなし",
    "-sC": "デフォルトスクリプト (-sC)",
    "safe": "安全なスクリプト (safe)",
}

# 実際のnmapコマンドがない環境や安全のために模倣するモックデータ
MOCK_TARGETS = {
    TARGET_IP: {
        "status": "up",
        "ports": [
            {
                "port": 22,
                "protocol": "tcp",
                "state": "open",
                "service": "ssh",
                "version": "OpenSSH 8.9p1 Ubuntu",
            },
            {
                "port": 80,
                "protocol": "tcp",
                "state": "open",
                "service": "http",
                "version": "Apache httpd 2.4.41",
            },
            {
                "port": 443,
                "protocol": "tcp",
                "state": "open",
                "service": "https",
                "version": "Apache httpd 2.4.41",
            },
            {
                "port": 8081,
                "protocol": "tcp",
                "state": "open",
                "service": "http-alt",
                "version": "Werkzeug/Flask",
            },
        ],
    }
}


def is_valid_ports(ports: str) -> bool:
    """ポート指定の形式と範囲（1-65535）をチェック (例: 1-1024, 80,443)"""
    if not ports:
        return True
    if not re.match(r"^[0-9,-]+$", ports):
        return False

    for part in ports.split(","):
        if not part:
            return False
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                return False
            start_p, end_p = int(bounds[0]), int(bounds[1])
            if not (1 <= start_p <= 65535 and 1 <= end_p <= 65535 and start_p <= end_p):
                return False
        else:
            if not part.isdigit():
                return False
            p = int(part)
            if not (1 <= p <= 65535):
                return False

    return True


@namp.route("/")
def index():
    return render_template(
        "nmap.html",
        scan_types=ALLOWED_SCAN_TYPES,
        scripts=ALLOWED_SCRIPTS,
    )


@namp.route("/api/scan", methods=["POST"])
def scan():
    data = request.get_json(silent=True) or {}

    # ターゲットを 192.168.111.129 に完全固定
    target = TARGET_IP

    scan_type = str(data.get("scan_type", "-sT")).strip()
    ports = str(data.get("ports", "1-1024")).strip()
    script_option = str(data.get("script", "none")).strip()

    # バリデーション
    if scan_type not in ALLOWED_SCAN_TYPES:
        return jsonify({"error": "許可されていないスキャンタイプです。"}), 400
    if scan_type != "-sn" and not is_valid_ports(ports):
        return jsonify({"error": "無効なポート指定です（1〜65535の数値または範囲を指定してください）。"}), 400
    if script_option not in ALLOWED_SCRIPTS:
        return jsonify({"error": "無効なスクリプトオプションです。"}), 400

    # コマンドの組み立て
    cmd = ["nmap", scan_type]

    if script_option == "-sC":
        cmd.append("-sC")
    elif script_option != "none":
        cmd.append(f"--script={script_option}")

    if scan_type != "-sn" and ports:
        cmd.extend(["-p", ports])

    cmd.append(target)

    # システムに nmap がインストールされているか確認
    nmap_path = shutil.which("nmap")

    if not nmap_path:
        target_info = MOCK_TARGETS.get(target, {"ports": []})
        output = f"Starting Nmap (Mock Mode - nmap not found on host) for {target}\n"
        output += "----------------------------------------------------\n"
        output += "PORT     STATE     SERVICE   VERSION\n"
        for p in target_info["ports"]:
            port_proto = f"{p['port']}/{p['protocol']}".ljust(8)
            state = p["state"].ljust(9)
            service = p["service"].ljust(9)
            output += f"{port_proto} {state} {service} {p['version']}\n"
        output += "----------------------------------------------------\n"
        output += "Nmap done: 1 IP address (1 host up) scanned in 0.15 seconds.\n"

        return jsonify({
            "command": " ".join(cmd) + " (Executed in Safe Mock Mode)",
            "output": output,
        })

    # 実際にnmapがインストールされている場合はサブプロセスで実行
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return jsonify({
                "command": " ".join(cmd),
                "error": result.stderr.strip() or "Nmapの実行中にエラーが発生しました。",
            }), 500

        return jsonify({
            "command": " ".join(cmd),
            "output": result.stdout,
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "スキャンがタイムアウトしました（60秒超過）。"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500