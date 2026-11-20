import re
import subprocess
from flask import Blueprint, jsonify, render_template, request

# Blueprintの定義 (URLプレフィックスは app.py 側で /nc などに登録想定)
nc_bp = Blueprint("nc", __name__, template_folder="templates")

# 許可する Netcat の操作モード（ホワイトリスト）
ALLOWED_MODES = {
    "port_check": "ポート疎通確認 (nc -zv -w 2)",
    "banner_grab": "バナー取得 / 接続応答確認 (nc -v -w 2)",
    "http_head": "HTTP ヘッダ取得 (HEAD / HTTP/1.0 送信)",
}


def is_valid_port(port_str: str) -> bool:
  """単一ポート番号（1〜65535）の厳格なバリデーション"""
  if not port_str.isdigit():
    return False
  port_num = int(port_str)
  return 1 <= port_num <= 65535


@nc_bp.route("/")
def index():
  return render_template("nc.html", modes=ALLOWED_MODES)


@nc_bp.route("/api/exec", methods=["POST"])
def execute_nc():
  data = request.get_json() or {}

  # セキュリティのためターゲットを 172.0.0.1 に完全固定
  target = "192.168.6.14"

  mode = data.get("mode", "port_check").strip()
  port = str(data.get("port", "80")).strip()

  # バリデーション
  if mode not in ALLOWED_MODES:
    return jsonify({"error": "許可されていない実行モードです。"}), 400
  if not is_valid_port(port):
    return (
        jsonify({"error": "ポート番号は 1〜65535 の数値で指定してください。"}),
        400,
    )

  # モードごとの安全なコマンド組み立て
  stdin_payload = None
  if mode == "port_check":
    # -z: ゼロI/Oモード(スキャン), -v: 詳細出力, -w 2: タイムアウト2秒
    cmd = ["nc", "-zv", "-w", "2", target, port]
    display_cmd = " ".join(cmd)
  elif mode == "banner_grab":
    # 接続して相手の最初の応答（SSHバナーなど）だけを受け取る
    cmd = ["nc", "-v", "-w", "2", target, port]
    stdin_payload = ""
    display_cmd = " ".join(cmd)
  elif mode == "http_head":
    # HTTPサーバーに対して安全な HEAD リクエストを送信
    cmd = ["nc", "-v", "-w", "2", target, port]
    stdin_payload = "HEAD / HTTP/1.0\r\n\r\n"
    display_cmd = f'printf "HEAD / HTTP/1.0\\r\\n\\r\\n" | {" ".join(cmd)}'

  try:
    result = subprocess.run(
        cmd,
        input=stdin_payload,
        capture_output=True,
        text=True,
        timeout=10,
        encoding="utf-8",
        errors="replace",
    )

    # 注意: nc -zv は接続成功メッセージも標準エラー出力(stderr)に出す仕様のため両方結合する
    combined_output = ""
    if result.stdout:
      combined_output += result.stdout
    if result.stderr:
      combined_output += result.stderr

    if not combined_output.strip():
      combined_output = "(応答なし / タイムアウト)"

    return jsonify({
        "command": display_cmd,
        "output": combined_output,
        "returncode": result.returncode,
    })

  except subprocess.TimeoutExpired:
    return jsonify({"error": "接続がタイムアウトしました。"}), 504
  except FileNotFoundError:
    return (
        jsonify({
            "error": (
                "システムに 'nc' (netcat) がインストールされていません。"
            )
        }),
        500,
    )
  except Exception as e:
    return jsonify({"error": str(e)}), 500