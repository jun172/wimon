import asyncio
import json
import os
from datetime import datetime
from urllib.parse import urlparse
import aiohttp
from flask import Blueprint, jsonify, render_template, request

# FlaskのBlueprint定義
stress_bp = Blueprint("stress_lab", __name__, template_folder="templates")

# ログファイル名
STRESS_LOG_FILE = "stress_activity_logs.json"

# 安全装置：ローカル環境以外への実行を防ぐ
ALLOWED_HOSTS = {"192.168.6.24", "localhost", "127.0.0.1"}


def record_stress_log(entry_data):
  """負荷テストの実行履歴をJSONファイルに保存するヘルパー関数"""
  logs = []
  if os.path.exists(STRESS_LOG_FILE):
    try:
      with open(STRESS_LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)
    except Exception:
      logs = []

  logs.insert(0, entry_data)
  logs = logs[:50]  # 最新50件まで保持

  try:
    with open(STRESS_LOG_FILE, "w", encoding="utf-8") as f:
      json.dump(logs, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


async def send_request(session, url, results):
  import time

  start_time = time.perf_counter()
  try:
    async with session.get(url, timeout=5) as response:
      await response.read()
      elapsed = time.perf_counter() - start_time
      results.append({"status": response.status, "latency": elapsed})
  except Exception as e:
    elapsed = time.perf_counter() - start_time
    results.append({"status": "ERROR", "latency": elapsed, "error": str(e)})


async def run_load_test_async(url, total_requests, concurrency):
  parsed = urlparse(url)
  if parsed.hostname not in ALLOWED_HOSTS:
    raise ValueError(
        "安全のため、許可されたローカル環境以外へのテストは制限されています。"
    )

  results = []
  semaphore = asyncio.Semaphore(concurrency)

  async def bounded_request(session):
    async with semaphore:  # 修正: xwith -> with
      await send_request(session, url, results)

  import time

  start_test = time.perf_counter()
  async with aiohttp.ClientSession() as session:
    tasks = [bounded_request(session) for _ in range(total_requests)]
    await asyncio.gather(*tasks)
  total_time = time.perf_counter() - start_test

  if not results:
    return {
        "total_requests": total_requests,
        "concurrency": concurrency,
        "total_time_sec": 0,
        "success_count": 0,
        "fail_count": total_requests,
        "avg_latency_ms": 0,
        "requests_per_sec": 0,
    }

  success_count = sum(1 for r in results if r["status"] == 200)
  fail_count = total_requests - success_count
  valid_latencies = [
      r["latency"] for r in results if isinstance(r["latency"], float)
  ]
  avg_latency = (
      (sum(valid_latencies) / len(valid_latencies)) if valid_latencies else 0
  )
  rps = total_requests / total_time if total_time > 0 else 0

  return {
      "total_requests": total_requests,
      "concurrency": concurrency,
      "total_time_sec": round(total_time, 2),
      "success_count": success_count,
      "fail_count": fail_count,
      "avg_latency_ms": round(avg_latency * 1000, 2),
      "requests_per_sec": round(rps, 2),
  }


@stress_bp.route("/")
def index():
  return render_template("ddos.html")


@stress_bp.route("/api/stress", methods=["POST"])
def run_stress():
  data = request.get_json() or {}
  url = data.get("url", "http://127.0.0.1:8081/")

  total_requests = min(int(data.get("requests", 50)), 200)
  concurrency = min(int(data.get("concurrency", 10)), 20)

  try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
      stats = loop.run_until_complete(
          run_load_test_async(url, total_requests, concurrency)
      )
    finally:
      loop.close()

    # 📝 テスト結果をログとして記録
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_url": url,
        **stats,
    }
    record_stress_log(log_entry)

    return jsonify(
        {
            "status": "success",
            "command": (
                f"aiohttp-load-test -n {total_requests} -c {concurrency} {url}"
            ),
            **stats,
        }
    )
  except ValueError as ve:
    return jsonify({"error": str(ve)}), 400
  except Exception as e:
    return jsonify({"error": str(e)}), 500


# 🌐 負荷テストの実行履歴をWeb画面で確認するためのAPI
@stress_bp.route("/api/stress/logs", methods=["GET"])
def get_stress_logs():
  logs = []
  if os.path.exists(STRESS_LOG_FILE):
    try:
      with open(STRESS_LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)
    except Exception:
      logs = []
  return jsonify(logs)