import re
import shutil
import subprocess
from flask import Blueprint, jsonify, render_template, request

# Blueprintの定義
namp = Blueprint("nmap", __name__, template_folder="templates")

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
    "172.0.0.1": {
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
                "port": 8080,
                "protocol": "tcp",
                "state": "open",
                "service": "http-proxy",
                "version": "Node.js Express",
            },
        ],
    }
}


def is_valid_ports(ports: str) -> bool:
  """ポート指定の形式チェック (例: 1-1024, 80,443)"""
  if not ports:
    return True
  pattern = r"^[0-9,-]+$"
  return bool(re.match(pattern, ports))


@namp.route("/")
def index():
  return render_template(
      "nmap.html", scan_types=ALLOWED_SCAN_TYPES, scripts=ALLOWED_SCRIPTS
  )


@namp.route("/api/scan", methods=["POST"])
def scan():
  data = request.get_json() or {}

  # セキュリティのためターゲットを 172.0.0.1 に完全固定
  target = "172.0.0.1"

  scan_type = data.get("scan_type", "-sT").strip()
  ports = data.get("ports", "1-1024").strip()
  script_option = data.get("script", "none").strip()

  # バリデーション
  if scan_type not in ALLOWED_SCAN_TYPES:
    return jsonify({"error": "許可されていないスキャンタイプです。"}), 400
  if scan_type != "-sn" and not is_valid_ports(ports):
    return jsonify({"error": "無効なポート指定です。"}), 400
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
    # 【フォールバック機構】nmapが未導入の環境でもエラーにせず、学習用の模擬結果を返す（Pythonの ljust を使用）
    target_info = MOCK_TARGETS[target]
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
        cmd, capture_output=True, text=True, timeout=60, encoding="utf-8"
    )
    if result.returncode != 0:
      return (
          jsonify({
              "command": " ".join(cmd),
              "error": (
                  result.stderr or "Nmapの実行中にエラーが発生しました。"
              ),
          }),
          500,
      )

    return jsonify({"command": " ".join(cmd), "output": result.stdout})

  except subprocess.TimeoutExpired:
    return (
        jsonify({"error": "スキャンがタイムアウトしました（60秒超過）。"}),
        504,
    )
  except Exception as e:
    return jsonify({"error": str(e)}), 500