import re
import shutil
import subprocess
from flask import Blueprint, jsonify, render_template, request

# Blueprintの定義 (WEB.py 側で app.register_blueprint(nc_bp, url_prefix="/nc") 登録想定)
nc_bp = Blueprint("nc", __name__, template_folder="templates")

TARGET_IP = "192.168.111.129"
MAX_PORTS_PER_REQUEST = 64
MAX_OUTPUT_CHARS = 1500

# 許可する Netcat の操作モード（ホワイトリスト）
ALLOWED_MODES = {
    "port_check": "ポート疎通確認 (nc -zv -w 2)",
    "banner_grab": "バナー取得 / 接続応答確認 (nc -v -w 2)",
    "http_head": "HTTP ヘッダ取得 (HEAD / HTTP/1.0 送信)",
    "http_get": "HTTP レスポンス確認 (GET / HTTP/1.0 送信)",
    "tls_check": "TLS/SSL 証明書確認 (openssl s_client)",
}

# オフライン・サンドボックス演習用のモック情報
MOCK_PORTS = {
    21: {"open": True, "service": "ftp", "banner": "220 (vsFTPd 3.0.3)"},
    22: {"open": True, "service": "ssh", "banner": "SSH-2.0-OpenSSH_8.9p1 Ubuntu"},
    53: {"open": True, "service": "domain", "banner": "DNS service port 53 (tcp) open"},
    80: {
        "open": True,
        "service": "http",
        "banner": "HTTP/1.1 200 OK\r\nServer: Apache/2.4.41 (Ubuntu)\r\nContent-Type: text/html; charset=UTF-8",
    },
    88: {"open": True, "service": "kerberos-sec", "banner": "Kerberos v5 (tcp/88) listening"},
    135: {"open": True, "service": "msrpc", "banner": "Microsoft RPC Endpoint Mapper (tcp/135) open"},
    139: {"open": True, "service": "netbios-ssn", "banner": "NetBIOS Session Service (tcp/139) open"},
    389: {"open": True, "service": "ldap", "banner": "LDAP service (tcp/389) open"},
    443: {
        "open": True,
        "service": "https",
        "banner": "HTTP/1.1 200 OK\r\nServer: Apache/2.4.41 (Ubuntu)\r\nTLSv1.3 / Subject: CN=192.168.111.129",
    },
    445: {"open": True, "service": "microsoft-ds", "banner": "SMB service (tcp/445) open"},
    636: {"open": True, "service": "ldapssl", "banner": "LDAPS service (tcp/636) open"},
    1433: {"open": True, "service": "ms-sql-s", "banner": "MSSQL TDS service (tcp/1433) open"},
    3306: {"open": True, "service": "mysql", "banner": "8.0.36-0ubuntu0.22.04.1"},
    3389: {"open": True, "service": "ms-wbt-server", "banner": "RDP service (tcp/3389) open"},
    5432: {"open": True, "service": "postgresql", "banner": "PostgreSQL 15.4"},
    5985: {"open": True, "service": "wsman", "banner": "WinRM HTTPAPI service (tcp/5985) open"},
    8080: {
        "open": True,
        "service": "http-proxy",
        "banner": "HTTP/1.1 200 OK\r\nServer: Node.js Express",
    },
    8081: {
        "open": True,
        "service": "http-alt",
        "banner": "HTTP/1.1 200 OK\r\nServer: Werkzeug/3.0.0 Python/3.11.0",
    },
    8443: {
        "open": True,
        "service": "https-alt",
        "banner": "HTTP/1.1 200 OK\r\nServer: Jetty / Management Console",
    },
}


def parse_ports_spec(ports_raw: str) -> list[int] | None:
    """
    単一ポート（80）、カンマ区切り（80,443,3389）、範囲（20-25）を解析してポートリストを返す。
    総数が多すぎる場合は安全のため制限（最大64ポート）。
    """
    text = str(ports_raw).strip()
    if not text or not re.fullmatch(r"[0-9,-]+", text):
        return None

    result_ports: list[int] = []
    for part in text.split(","):
        if not part:
            return None
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                return None
            start_p, end_p = int(bounds[0]), int(bounds[1])
            if not (1 <= start_p <= 65535 and 1 <= end_p <= 65535 and start_p <= end_p):
                return None
            if (end_p - start_p + 1) > MAX_PORTS_PER_REQUEST:
                return None
            result_ports.extend(range(start_p, end_p + 1))
        else:
            if not part.isdigit():
                return None
            p = int(part)
            if not (1 <= p <= 65535):
                return None
            result_ports.append(p)

    unique_ports = list(dict.fromkeys(result_ports))
    if not unique_ports or len(unique_ports) > MAX_PORTS_PER_REQUEST:
        return None
    return unique_ports


def build_nc_command(target: str, port: int, mode: str) -> tuple[list[str], str | None, str]:
    """モードに応じたコマンド・標準入力・表示用コマンド文字列を組み立てる"""
    p_str = str(port)
    if mode == "port_check":
        cmd = ["nc", "-zv", "-w", "2", target, p_str]
        return cmd, None, " ".join(cmd)
    if mode == "banner_grab":
        cmd = ["nc", "-v", "-w", "2", target, p_str]
        return cmd, "\r\n", " ".join(cmd)
    if mode == "http_head":
        cmd = ["nc", "-v", "-w", "2", target, p_str]
        payload = f"HEAD / HTTP/1.0\r\nHost: {target}\r\nConnection: close\r\n\r\n"
        return cmd, payload, f'printf "HEAD / HTTP/1.0\\r\\nHost: {target}\\r\\n\\r\\n" | {" ".join(cmd)}'
    if mode == "http_get":
        cmd = ["nc", "-v", "-w", "2", target, p_str]
        payload = f"GET / HTTP/1.0\r\nHost: {target}\r\nConnection: close\r\n\r\n"
        return cmd, payload, f'printf "GET / HTTP/1.0\\r\\nHost: {target}\\r\\n\\r\\n" | {" ".join(cmd)}'
    if mode == "tls_check":
        cmd = ["openssl", "s_client", "-connect", f"{target}:{p_str}", "-brief"]
        return cmd, "Q\n", " ".join(cmd)

    cmd = ["nc", "-zv", "-w", "2", target, p_str]
    return cmd, None, " ".join(cmd)


def mock_fallback(target: str, port: int, mode: str) -> str:
    """実接続できない・コマンド不在時の模擬出力"""
    info = MOCK_PORTS.get(port)
    if not info or not info.get("open"):
        return f"[Mock] nc: connect to {target} port {port} (tcp) failed: Connection refused"

    if mode == "port_check":
        return f"[Mock] Connection to {target} {port} port [tcp/{info['service']}] succeeded!"
    if mode in ("http_head", "http_get"):
        return f"[Mock] ({target}:{port})\n{info['banner']}"
    if mode == "tls_check":
        return f"[Mock] TLS handshake info for {target}:{port} -> {info['banner']}"
    return f"[Mock] Connected to {target}:{port} ({info['service']})\n{info['banner']}"


def run_single_port(target: str, port: int, mode: str, has_nc: bool, has_openssl: bool) -> tuple[str, str]:
    """1ポート分の実行を行い、(表示コマンド, 出力テキスト) を返す"""
    cmd, stdin_payload, display_cmd = build_nc_command(target, port, mode)
    tool_name = cmd[0]

    if (tool_name == "nc" and not has_nc) or (tool_name == "openssl" and not has_openssl):
        return display_cmd, mock_fallback(target, port, mode)

    try:
        result = subprocess.run(
            cmd,
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=6,
            encoding="utf-8",
            errors="replace",
        )
        combined = f"{result.stdout or ''}{result.stderr or ''}".strip()

        if not combined:
            combined = mock_fallback(target, port, mode)

        if len(combined) > MAX_OUTPUT_CHARS:
            combined = combined[:MAX_OUTPUT_CHARS] + "\n... (出力が長いため省略しました)"

        return display_cmd, combined

    except subprocess.TimeoutExpired:
        return display_cmd, mock_fallback(target, port, mode)
    except Exception as e:
        return display_cmd, f"[ERROR] {e}"


@nc_bp.route("/")
def index():
    return render_template("nc.html", modes=ALLOWED_MODES, target_ip=TARGET_IP)


@nc_bp.route("/api/run", methods=["POST"])
@nc_bp.route("/api/exec", methods=["POST"])
def execute_nc():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    target = TARGET_IP
    raw_mode = data.get("mode", "port_check")
    raw_port = data.get("port", "80")

    mode = raw_mode.strip() if isinstance(raw_mode, str) else "port_check"
    port_text = str(raw_port).strip() if raw_port is not None else "80"

    if mode not in ALLOWED_MODES:
        return jsonify({"error": "許可されていない実行モードです。"}), 400

    ports = parse_ports_spec(port_text)
    if ports is None:
        return jsonify({
            "error": "ポート指定が無効です（1〜65535の数値、カンマ区切り、または64ポート以内の範囲を指定してください）。"
        }), 400

    has_nc = shutil.which("nc") is not None
    has_openssl = shutil.which("openssl") is not None

    commands_used: list[str] = []
    sections: list[str] = []

    for p in ports:
        disp_cmd, out_text = run_single_port(target, p, mode, has_nc, has_openssl)
        commands_used.append(disp_cmd)
        if len(ports) > 1:
            sections.append(f"--- Port {p} ({disp_cmd}) ---\n{out_text}")
        else:
            sections.append(out_text)

    summary_cmd = " ; ".join(commands_used[:3]) + (" ..." if len(commands_used) > 3 else "")

    return jsonify({
        "target": target,
        "ports": ports,
        "command": summary_cmd,
        "output": "\n\n".join(sections),
    })