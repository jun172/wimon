import time
from flask import Blueprint, render_template, request

# Blueprintの定義
brute_bp = Blueprint(
    "brute_4digit", __name__, template_folder="templates"
)


@brute_bp.route("/", methods=["GET", "POST"])
def index():
  result = None
  log_lines = [
      "[SYSTEM] 4桁PINコード 高速ブルートフォース・エンジン稼働中...",
      "[INFO] ターゲットIDと4桁のPINを指定し、総当たり攻撃を発動してください。",
  ]

  if request.method == "POST":
    target_id = request.form.get("target_id", "admin").strip()
    
    # 🔴 ここでHTMLの入力欄（name="secret_pass"）から確実に値を受け取る
    target_pin = request.form.get("secret_pass", "").strip()

    # 入力値のバリデーション（4桁の数字か）
    if not target_pin.isdigit() or len(target_pin) != 4:
      log_lines.append(
          "[ERROR] パスワード欄には4桁の数字（例: 7942）を入力してください。"
      )
      return render_template("brute.html", result=None, log=log_lines)

    start_time = time.time()
    attempts = 0
    found = None

    log_lines.append(f"[+] ターゲットID: {target_id} | ターゲットPIN: {target_pin}")
    log_lines.append("[+] 探索空間: 0000 〜 9999 (1万通り)")
    log_lines.append("[*] 0000から順次フルスピードで総当たり演算を開始します...")

    temp_logs = []

    # 0000 から 9999 まで一気に総当たり
    for i in range(10000):
      attempts += 1
      guess = f"{i:04d}"  # 4桁のゼロ埋め文字列 (0000, 0001, ...)

      # ログが多すぎないよう間引く、または一致時に記録
      if attempts % 500 == 0 or guess == target_pin:
        temp_logs.append(
            f"[*] 試行中... PIN: [ {guess} ] -> 拒否 (試行: {attempts:,}回)"
        )

      # ユーザーが入力した target_pin と一致したか判定
      if guess == target_pin:
        found = guess
        temp_logs.append(
            f"[✔ CRITICAL SUCCESS] 4桁PINコード突破成功！ → 発見されたコード:"
            f" [{found}]"
        )
        break

    if not found:
      found = target_pin
      temp_logs.append(
          f"[✔ CRITICAL SUCCESS] 4桁PINコード突破成功！ → 発見されたコード:"
          f" [{found}]"
      )

    elapsed = round(time.time() - start_time, 3)
    log_lines.extend(temp_logs)
    log_lines.append(
        f"[+] 完了: 総試行回数 {attempts:,}回 | 処理時間: {elapsed}秒"
    )

    result = {
        "ip": "192.168.6.14",
        "attempts": attempts,
        "elapsed": elapsed,
        "found": found,
        "total_space": "10,000通り (10^4)",
    }

  return render_template("brute.html", result=result, log=log_lines)