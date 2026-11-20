import time
from flask import Blueprint, render_template, request

# Gobuster用 Blueprint の定義
gobuster_bp = Blueprint("gobuster", __name__, template_folder="templates")


@gobuster_bp.route("/", methods=["GET", "POST"])
def index():
  result = None
  log_lines = [
      "[SYSTEM] Gobuster v3.6 [Directory Bruteforce Module] 稼働中...",
      (
          "[INFO] 拡張ワードリストを読み込みました。"
          "ターゲットの隠しパス・機密ファイルの総当たりスキャンを開始します。"
      ),
  ]

  if request.method == "POST":
    target_url = request.form.get(
        "target_url", "http://192.168.5.179:8081"
    ).strip()
    wordlist_type = request.form.get("wordlist", "common").strip()

    start_time = time.time()
    attempts = 0
    found_paths = []

    log_lines.append(f"[+] ターゲットURL: {target_url}")
    log_lines.append(f"[+] 使用ワードリスト: {wordlist_type}_extended.txt (拡張パス集)")
    log_lines.append("[*] ワードリスト展開完了。高速スキャンを開始します...\n")

    # 拡張された本格的なダミーパスリスト（約40種類）
    paths_to_scan = [
        # 管理画面・認証関連
        "admin",
        "administrator",
        "login",
        "signin",
        "signup",
        "dashboard",
        "manage",
        "manager",
        "auth",
        "portal",
        # API・システム関連
        "api",
        "v1",
        "v2",
        "graphql",
        "swagger-ui.html",
        "metrics",
        "health",
        "status",
        # 設定・データ・バックアップ
        "config.json",
        "config.php",
        "settings.py",
        "db.sql",
        "database.sqlite",
        "backup.zip",
        "backup.tar.gz",
        "dump.sql",
        "old",
        "test",
        # 開発・デバッグ・隠しファイル
        "phpinfo.php",
        "info.php",
        "robots.txt",
        "sitemap.xml",
        ".env",
        ".git/HEAD",
        ".git/config",
        "uploads",
        "images",
        "assets",
        "server-status",
        "secret",
        "private",
    ]

    temp_logs = []

    for path in paths_to_scan:
      attempts += 1
      time.sleep(0.02)  # スキャンの演出用ウェイト（少しテンポよく）

      # ヒットさせるパスの判定ロジック
      if path in [
          "admin",
          "login",
          "dashboard",
          "config.json",
          "backup.zip",
          "api",
          ".env",
          ".git/HEAD",
          "secret",
      ]:
        status = "Status: 200 (OK)"
        found_paths.append(f"/{path}")
        temp_logs.append(f"/[{path}] (Status: 200) [Size: 1420] -> HIT!")
      elif path in [
          "administrator",
          "manage",
          "db.sql",
          "backup.tar.gz",
          "private",
      ]:
        status = "Status: 301 (Moved Permanently)"
        temp_logs.append(f"/[{path}] (Status: 301) [Size: 178] -> Redirect")
      elif path in ["uploads", "api/v1", "swagger-ui.html", "robots.txt"]:
        status = "Status: 403 (Forbidden)"
        temp_logs.append(f"/[{path}] (Status: 403) [Size: 312]")
      else:
        temp_logs.append(f"/[{path}] (Status: 404) [Size: 0]")

    elapsed = round(time.time() - start_time, 3)
    log_lines.extend(temp_logs)
    log_lines.append(
        f"\n[+] スキャン完了: 総チェック数 {attempts}件 | 発見パス数:"
        f" {len(found_paths)}件 | 処理時間: {elapsed}秒"
    )

    result = {
        "ip": "192.168.6.14",
        "attempts": attempts,
        "elapsed": elapsed,
        "found_count": len(found_paths),
        "found_paths": found_paths,
    }

  return render_template("gobuster.html", result=result, log=log_lines)