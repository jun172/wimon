import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import aiohttp
from flask import Blueprint, jsonify, render_template, request

stress_bp = Blueprint("stress_lab", __name__, template_folder="templates")

BASE_DIR = Path(__file__).resolve().parent
STRESS_LOG_FILE = BASE_DIR / "stress_activity_logs.json"

# ターゲットURLと許可ホストを 192.168.111.129:8081 に固定
FIXED_TARGET_URL = "http://192.168.111.129:8081/"
ALLOWED_HOSTS = {"192.168.111.129"}
MAX_REQUESTS = 200
MAX_CONCURRENCY = 20


def record_stress_log(entry_data: dict) -> None:
    """負荷テストの実行履歴をJSONファイルに保存するヘルパー関数"""
    logs = []
    if STRESS_LOG_FILE.exists():
        try:
            logs = json.loads(STRESS_LOG_FILE.read_text(encoding="utf-8"))
            if not isinstance(logs, list):
                logs = []
        except Exception:
            logs = []

    logs.insert(0, entry_data)
    logs = logs[:50]

    try:
        STRESS_LOG_FILE.write_text(
            json.dumps(logs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


async def send_request(session: aiohttp.ClientSession, url: str, results: list) -> None:
    start_time = time.perf_counter()
    try:
        async with session.get(url) as response:
            await response.read()
            elapsed = time.perf_counter() - start_time
            results.append({"status": response.status, "latency": elapsed})
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        results.append({"status": "ERROR", "latency": elapsed, "error": str(e)})


async def run_load_test_async(url: str, total_requests: int, concurrency: int) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(
            f"安全のため、ターゲットは {FIXED_TARGET_URL} に固定されています。"
        )

    results = []
    semaphore = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=5)

    async def bounded_request(session: aiohttp.ClientSession) -> None:
        async with semaphore:
            await send_request(session, url, results)

    start_test = time.perf_counter()
    async with aiohttp.ClientSession(timeout=timeout) as session:
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
    valid_latencies = [r["latency"] for r in results if isinstance(r["latency"], float)]
    avg_latency = (sum(valid_latencies) / len(valid_latencies)) if valid_latencies else 0
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
    return render_template("ddos.html", target_url=FIXED_TARGET_URL)


@stress_bp.route("/api/stress", methods=["POST"])
def run_stress():
    data = request.get_json(silent=True) or {}

    # 入力値に関わらずターゲットURLを固定
    url = FIXED_TARGET_URL

    try:
        raw_requests = int(data.get("requests", 50))
        raw_concurrency = int(data.get("concurrency", 10))
    except (TypeError, ValueError):
        return jsonify({"error": "requests と concurrency は整数で指定してください。"}), 400

    if raw_requests < 1 or raw_concurrency < 1:
        return jsonify({"error": "requests と concurrency は 1 以上を指定してください。"}), 400

    total_requests = min(raw_requests, MAX_REQUESTS)
    concurrency = min(raw_concurrency, MAX_CONCURRENCY)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            stats = loop.run_until_complete(
                run_load_test_async(url, total_requests, concurrency)
            )
        finally:
            loop.close()

        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_url": url,
            **stats,
        }
        record_stress_log(log_entry)

        return jsonify({
            "status": "success",
            "command": f"aiohttp-load-test -n {total_requests} -c {concurrency} {url}",
            **stats,
        })
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@stress_bp.route("/api/stress/logs", methods=["GET"])
def get_stress_logs():
    if not STRESS_LOG_FILE.exists():
        return jsonify([])
    try:
        logs = json.loads(STRESS_LOG_FILE.read_text(encoding="utf-8"))
        return jsonify(logs if isinstance(logs, list) else [])
    except Exception:
        return jsonify([])