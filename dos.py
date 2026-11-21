from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import ipaddress
import json
import os
import threading
import time
from urllib.parse import urlparse
from flask import Blueprint, jsonify, render_template, request
import requests
from requests.sessions import Session
from requests.exceptions import RequestException

dos_bp = Blueprint("dos_lab", __name__, template_folder="templates")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIT_LOG_FILE = os.path.join(BASE_DIR, "stress_audit_logs.json")

MAX_REQUESTS = 2000
MAX_CONCURRENCY = 2000
REQUEST_TIMEOUT_SEC = 0.1
MAX_SAVED_LOGS = 1000

log_lock = threading.Lock()


def is_safe_target_url(url: str) -> tuple[bool, str]:
  """ローカルまたはプライベートネットワーク宛てのHTTP/HTTPS URLか検証する"""
  parsed = urlparse((url or "").strip())
  if parsed.scheme not in ("http", "https"):
    return False, "URLは http:// または https:// で指定してください"

  host = (parsed.hostname or "").strip().lower()
  if not host:
    return False, "ホスト名が指定されていません"

  if host in ("localhost", "::1"):
    return True, ""

  try:
    ip_obj = ipaddress.ip_address(host)
    if ip_obj.is_loopback or ip_obj.is_private:
      return True, ""
  except ValueError:
    pass

  return (
      False,
      "安全のため、localhost / 192.168.111.129 / プライベートIP宛てのみ許可されています",
  )


def load_audit_logs() -> list[dict]:
  with log_lock:
    if os.path.exists(AUDIT_LOG_FILE):
      try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
          if isinstance(data, list):
            return data
      except Exception:
        pass
    return []


def append_audit_log(entry: dict) -> None:
  with log_lock:
    logs = []
    if os.path.exists(AUDIT_LOG_FILE):
      try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
          loaded = json.load(f)
          if isinstance(loaded, list):
            logs = loaded
      except Exception:
        logs = []

    logs.insert(0, entry)
    logs = logs[:MAX_SAVED_LOGS]

    try:
      with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
      pass


def _send_single_request(url: str) -> tuple[bool, float]:
  """1リクエスト送信し、(成功フラグ, レイテンシms) を返す"""
  start = time.perf_counter()
  try:
    with Session() as sess:
      resp = sess.get(url, timeout=REQUEST_TIMEOUT_SEC)
      elapsed_ms = (time.perf_counter() - start) * 1000.0
      ok = 200 <= resp.status_code < 500
      return ok, elapsed_ms
  except RequestException:
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return False, elapsed_ms
  

def run_stress_test(url: str, total_requests: int, concurrency: int) -> dict:
  """指定回数・同時接続数でストレステストを実行し、集計結果を返す"""
  started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  wall_start = time.perf_counter()

  success_count = 0
  fail_count = 0
  latencies_ms: list[float] = []

  workers = min(concurrency, total_requests)
  with ThreadPoolExecutor(max_workers=workers) as executor:
    futures = [executor.submit(_send_single_request, url) for _ in range(total_requests)]
    for fut in as_completed(futures):
      ok, elapsed_ms = fut.result()
      latencies_ms.append(elapsed_ms)
      if ok:
        success_count += 1
      else:
        fail_count += 1

  total_time_sec = max(time.perf_counter() - wall_start, 0.0001)
  avg_latency_ms = (
      sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
  )
  requests_per_sec = total_requests / total_time_sec

  result = {
      "timestamp": started_at,
      "target_url": url,
      "command": f"stress -u {url} -n {total_requests} -c {concurrency}",
      "total_requests": total_requests,
      "concurrency": concurrency,
      "total_time_sec": round(total_time_sec, 3),
      "success_count": success_count,
      "fail_count": fail_count,
      "avg_latency_ms": round(avg_latency_ms, 2),
      "requests_per_sec": round(requests_per_sec, 2),
  }
  append_audit_log(result)
  return result


@dos_bp.route("/")
def index():
  return render_template("dos.html")


@dos_bp.route("/api/stress", methods=["POST"])
def api_run_stress():
  data = request.get_json(silent=True) or {}
  url = str(data.get("url", "")).strip()

  try:
    total_requests = int(data.get("requests", 50))
    concurrency = int(data.get("concurrency", 10))
  except (TypeError, ValueError):
    return jsonify({"error": "requests と concurrency は整数で指定してください"}), 400

  is_safe, reason = is_safe_target_url(url)
  if not is_safe:
    return jsonify({"error": reason}), 400

  if not (1 <= total_requests <= MAX_REQUESTS):
    return (
        jsonify({"error": f"リクエスト数は 1〜{MAX_REQUESTS} の範囲で指定してください"}),
        400,
    )

  if not (1 <= concurrency <= MAX_CONCURRENCY):
    return (
        jsonify({"error": f"同時接続数は 1〜{MAX_CONCURRENCY} の範囲で指定してください"}),
        400,
    )

  result = run_stress_test(url, total_requests, concurrency)
  return jsonify(result), 200


@dos_bp.route("/api/stress/logs", methods=["GET"])
def api_get_stress_logs():
  return jsonify(load_audit_logs()), 200