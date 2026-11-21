#!/usr/bin/env python3
from collections.abc import Callable
from datetime import datetime
import hashlib
import io
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import sys
from flask import Blueprint, jsonify, render_template, request

c1_bp = Blueprint("c1_console", __name__, template_folder="templates")

BASE_DIR = Path(__file__).resolve().parent
SANDBOX_ROOT = (BASE_DIR / "sandbox").resolve()

COMMAND_CATALOG = {
    "pwd": "現在の作業ディレクトリを表示する",
    "cd": "作業ディレクトリを移動する（cd / または cd ~ でルートへ）",
    "ls": "ファイル・ディレクトリ一覧を表示する（-l, -a 対応）",
    "tree": "ディレクトリ構造をツリー表示する",
    "clear": "画面をクリアする",
    "help": "利用可能コマンド一覧を表示する",
    "touch": "空ファイル作成または更新時刻の更新",
    "mkdir": "ディレクトリを作成する（-p 対応）",
    "cp": "ファイルをコピーする（-r でディレクトリ対応）",
    "mv": "ファイルやディレクトリを移動・リネームする",
    "rm": "ファイルを削除する（サンドボックス内のみ、-r 対応）",
    "chmod": "権限（8進数 例: 0644, 0755）を変更する",
    "cat": "ファイルの中身を表示する",
    "head": "ファイルの先頭行を表示する（-n 行数）",
    "tail": "ファイルの末尾行を表示する（-n 行数）",
    "echo": "文字列出力、または > / >> でファイルへ書き込み",
    "wc": "行数・単語数・バイト数を集計する（-l, -w, -c）",
    "grep": "パターンに一致する行を検索する（-n, -i 対応）",
    "sort": "行を並び替える（-n, -u, -r 対応）",
    "uniq": "隣接する重複行を整理する（-c でカウント）",
    "cut": "区切り文字と列番号で抽出する（-d 区切り -f 列）",
    "awk": "空白区切りで列抽出する（例: awk '{print $1, $3}' file）",
    "diff": "2つのファイルの差分を比較する",
    "sha256sum": "ファイルの SHA-256 ハッシュを計算する",
    "find": "条件に一致するパスを検索する（-name 対応）",
    "stat": "ファイルの詳細情報を表示する",
    "id": "ユーザー/グループIDを表示する",
    "whoami": "現在の実効ユーザー名を表示する",
    "uname": "システム情報を表示する（-a 対応）",
    "env": "環境変数を表示する",
    "cmdlist": "100選コマンド一覧を表示する（Webでは外パネルへ案内）",
}

ALL_100_COMMANDS = [
    "pwd", "cd", "ls", "tree", "clear", "history", "man", "which", "type", "exit",
    "touch", "mkdir", "cp", "mv", "rm", "rmdir", "ln", "file", "stat", "basename",
    "dirname", "realpath", "mktemp", "shred", "dd", "cat", "tac", "head", "tail", "less",
    "more", "wc", "grep", "egrep", "cut", "awk", "sed", "sort", "uniq", "tr",
    "paste", "diff", "comm", "tee", "xargs", "find", "locate", "tar", "gzip", "bzip2",
    "xz", "zip", "rsync", "md5sum", "sha256sum", "chmod", "chown", "chgrp", "umask", "id",
    "whoami", "who", "w", "su", "sudo", "useradd", "usermod", "userdel", "passwd", "ps",
    "top", "htop", "pgrep", "pkill", "kill", "jobs", "fg", "bg", "nohup", "uptime",
    "uname", "free", "df", "du", "dmesg", "ip", "ss", "netstat", "ping", "traceroute",
    "curl", "wget", "dig", "nslookup", "nc", "ssh", "scp", "systemctl", "journalctl", "env",
    "export", "crontab", "alias",
]


def seed_sandbox_files() -> None:
    """演習ですぐ使えるサンプルファイル群をサンドボックスに初期配置"""
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    samples = {
        "logs/auth.log": (
            "2026-11-21 10:01:12 sshd[1021]: Accepted publickey for analyst from 192.168.111.10 port 51234\n"
            "2026-11-21 10:04:45 sshd[1088]: Failed password for invalid user admin from 192.168.111.200 port 44120\n"
            "2026-11-21 10:04:48 sshd[1089]: Failed password for invalid user admin from 192.168.111.200 port 44122\n"
            "2026-11-21 10:04:51 sshd[1090]: Failed password for invalid user admin from 192.168.111.200 port 44125\n"
            "2026-11-21 10:09:02 sudo: analyst : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/cat /etc/shadow\n"
        ),
        "logs/access.log": (
            "192.168.111.10 - - [21/Nov/2026:10:02:01 +0900] \"GET / HTTP/1.1\" 200 1420\n"
            "192.168.111.200 - - [21/Nov/2026:10:05:10 +0900] \"GET /admin/.env HTTP/1.1\" 404 196\n"
            "192.168.111.200 - - [21/Nov/2026:10:05:11 +0900] \"GET /wp-login.php HTTP/1.1\" 404 196\n"
            "192.168.111.15 - - [21/Nov/2026:10:06:30 +0900] \"POST /api/stress HTTP/1.1\" 200 512\n"
        ),
        "configs/app.conf": (
            "HOST=192.168.111.129\n"
            "PORT=8081\n"
            "DEBUG=false\n"
            "SANDBOX_ONLY=true\n"
        ),
        "notes/incident_memo.txt": (
            "初動チェック項目:\n"
            "1. auth.log から不審なログイン試行IPを特定する\n"
            "2. access.log から 404 スキャンや異常なリクエストを確認する\n"
            "3. sha256sum で重要ファイルのハッシュを記録する\n"
        ),
    }
    for rel_path, content in samples.items():
        dest = SANDBOX_ROOT / rel_path
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")


def to_real_cwd(v_cwd: str) -> Path:
    seed_sandbox_files()
    cleaned = (v_cwd or "/").lstrip("/")
    p = (SANDBOX_ROOT / cleaned).resolve()
    if p != SANDBOX_ROOT and SANDBOX_ROOT not in p.parents:
        return SANDBOX_ROOT
    return p if p.exists() and p.is_dir() else SANDBOX_ROOT


def to_virtual_path(real_path: Path) -> str:
    if real_path == SANDBOX_ROOT:
        return "/"
    return "/" + real_path.relative_to(SANDBOX_ROOT).as_posix()


def resolve_target(cwd: Path, target_str: str) -> Path:
    if target_str == "/":
        return SANDBOX_ROOT
    cleaned = target_str.lstrip("/")
    p = (cwd / cleaned).resolve()
    if p != SANDBOX_ROOT and SANDBOX_ROOT not in p.parents:
        raise ValueError(f"サンドボックス外へのアクセスは禁止されています: {target_str}")
    return p


class ShellContext:
    def __init__(self, cwd: Path, web_mode: bool = True):
        self.cwd = cwd
        self.web_mode = web_mode
        self.buf = io.StringIO()
        self.ok = True

    def out(self, msg: str = "") -> None:
        self.buf.write(msg + "\n")

    def fail(self, msg: str) -> None:
        self.out(msg)
        self.ok = False


def handle_help(ctx: ShellContext, args: list[str]) -> None:
    for k, desc in COMMAND_CATALOG.items():
        ctx.out(f"  {k:<11} : {desc}")


def handle_pwd(ctx: ShellContext, args: list[str]) -> None:
    ctx.out(f"{to_virtual_path(ctx.cwd)}  ({ctx.cwd})")


def handle_cd(ctx: ShellContext, args: list[str]) -> None:
    if not args or args[0] in ("~", "/"):
        ctx.cwd = SANDBOX_ROOT
        return
    dest = resolve_target(ctx.cwd, args[0])
    if not dest.exists():
        ctx.fail(f"cd: {args[0]}: ディレクトリが存在しません")
    elif not dest.is_dir():
        ctx.fail(f"cd: {args[0]}: ディレクトリではありません")
    else:
        ctx.cwd = dest


def handle_ls(ctx: ShellContext, args: list[str]) -> None:
    show_all = any(a.startswith("-") and "a" in a for a in args)
    long_fmt = any(a.startswith("-") and "l" in a for a in args)
    targets = [a for a in args if not a.startswith("-")] or ["."]
    for t in targets:
        p = resolve_target(ctx.cwd, t)
        if not p.exists():
            ctx.fail(f"ls: {t}: 見つかりません")
            continue
        entries = [p] if p.is_file() else sorted(p.iterdir())
        if not show_all:
            entries = [e for e in entries if not e.name.startswith(".")]
        for e in entries:
            suffix = "/" if e.is_dir() else ""
            if long_fmt:
                st = e.stat()
                ftype = "d" if e.is_dir() else "-"
                perms = stat.filemode(st.st_mode)[1:]
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M")
                ctx.out(f"{ftype}{perms}  {st.st_size:8d}  {mtime}  {e.name}{suffix}")
            else:
                ctx.out(f"{e.name}{suffix}")


def handle_tree(ctx: ShellContext, args: list[str]) -> None:
    start = resolve_target(ctx.cwd, args[0]) if args else ctx.cwd
    if not start.exists():
        ctx.fail(f"tree: {args[0]}: 見つかりません")
        return
    ctx.out(to_virtual_path(start))

    def _walk(d: Path, prefix: str) -> None:
        children = sorted(d.iterdir())
        for idx, ch in enumerate(children):
            is_last = idx == len(children) - 1
            conn = "└── " if is_last else "├── "
            suf = "/" if ch.is_dir() else ""
            ctx.out(f"{prefix}{conn}{ch.name}{suf}")
            if ch.is_dir():
                _walk(ch, prefix + ("    " if is_last else "│   "))

    if start.is_dir():
        _walk(start, "")


def handle_touch(ctx: ShellContext, args: list[str]) -> None:
    if not args:
        ctx.fail("touch: ファイル名を指定してください")
        return
    for name in args:
        p = resolve_target(ctx.cwd, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)
        os.utime(p, None)


def handle_mkdir(ctx: ShellContext, args: list[str]) -> None:
    parents = "-p" in args
    dirs = [a for a in args if a != "-p"]
    if not dirs:
        ctx.fail("mkdir: ディレクトリ名を指定してください")
        return
    for d in dirs:
        p = resolve_target(ctx.cwd, d)
        p.mkdir(parents=parents, exist_ok=not parents)


def handle_cp(ctx: ShellContext, args: list[str]) -> None:
    recursive = "-r" in args or "-R" in args
    paths = [a for a in args if not a.startswith("-")]
    if len(paths) < 2:
        ctx.fail("cp: コピー元とコピー先を指定してください")
        return
    src = resolve_target(ctx.cwd, paths[0])
    dst = resolve_target(ctx.cwd, paths[1])
    if not src.exists():
        ctx.fail(f"cp: {paths[0]}: 存在しません")
    elif src.is_dir() and not recursive:
        ctx.fail(f"cp: {paths[0]}: ディレクトリには -r が必要です")
    elif src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        if dst.is_dir():
            dst = dst / src.name
        shutil.copy2(src, dst)


def handle_mv(ctx: ShellContext, args: list[str]) -> None:
    paths = [a for a in args if not a.startswith("-")]
    if len(paths) < 2:
        ctx.fail("mv: 移動元と移動先を指定してください")
        return
    src = resolve_target(ctx.cwd, paths[0])
    dst = resolve_target(ctx.cwd, paths[1])
    if not src.exists():
        ctx.fail(f"mv: {paths[0]}: 存在しません")
        return
    if dst.is_dir():
        dst = dst / src.name
    shutil.move(str(src), str(dst))


def handle_rm(ctx: ShellContext, args: list[str]) -> None:
    recursive = "-r" in args or "-R" in args
    targets = [a for a in args if not a.startswith("-")]
    if not targets:
        ctx.fail("rm: 削除対象を指定してください")
        return
    for t in targets:
        p = resolve_target(ctx.cwd, t)
        if p == SANDBOX_ROOT:
            ctx.fail("rm: サンドボックスルートは削除できません")
        elif not p.exists():
            ctx.fail(f"rm: {t}: 存在しません")
        elif p.is_dir() and not recursive:
            ctx.fail(f"rm: {t}: ディレクトリには -r が必要です")
        elif p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()


def handle_chmod(ctx: ShellContext, args: list[str]) -> None:
    if len(args) < 2:
        ctx.fail("chmod: <8進権限 例:0644> <対象パス>")
        return
    mode_val = int(args[0], 8)
    for t in args[1:]:
        p = resolve_target(ctx.cwd, t)
        if not p.exists():
            ctx.fail(f"chmod: {t}: 存在しません")
        else:
            p.chmod(mode_val)
            ctx.out(f"{to_virtual_path(p)} -> {oct(mode_val)}")


def handle_echo(ctx: ShellContext, args: list[str]) -> None:
    if ">" in args or ">>" in args:
        op = ">>" if ">>" in args else ">"
        idx = args.index(op)
        text = " ".join(args[:idx])
        if idx + 1 >= len(args):
            ctx.fail("echo: リダイレクト先ファイルを指定してください")
            return
        dest = resolve_target(ctx.cwd, args[idx + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if op == ">>" else "w"
        with dest.open(mode, encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        ctx.out(" ".join(args))


def handle_cat(ctx: ShellContext, args: list[str]) -> None:
    if not args:
        ctx.fail("cat: ファイル名を指定してください")
        return
    for name in args:
        p = resolve_target(ctx.cwd, name)
        if not p.is_file():
            ctx.fail(f"cat: {name}: ファイルではありません")
        else:
            ctx.out(p.read_text(encoding="utf-8", errors="replace").rstrip("\n"))


def _head_tail(ctx: ShellContext, args: list[str], mode: str) -> None:
    n = 10
    files: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args):
            n = int(args[i + 1])
            i += 2
        else:
            files.append(args[i])
            i += 1
    if not files:
        ctx.fail(f"{mode}: ファイル名を指定してください")
        return
    for f in files:
        p = resolve_target(ctx.cwd, f)
        if not p.is_file():
            ctx.fail(f"{mode}: {f}: ファイルではありません")
        else:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[:n] if mode == "head" else lines[-n:]
            for ln in selected:
                ctx.out(ln)


def handle_head(ctx: ShellContext, args: list[str]) -> None:
    _head_tail(ctx, args, "head")


def handle_tail(ctx: ShellContext, args: list[str]) -> None:
    _head_tail(ctx, args, "tail")


def handle_wc(ctx: ShellContext, args: list[str]) -> None:
    show_l = "-l" in args
    show_w = "-w" in args
    show_c = "-c" in args
    if not (show_l or show_w or show_c):
        show_l = show_w = show_c = True
    for f in [a for a in args if not a.startswith("-")]:
        p = resolve_target(ctx.cwd, f)
        if not p.is_file():
            ctx.fail(f"wc: {f}: ファイルではありません")
        else:
            txt = p.read_text(encoding="utf-8", errors="replace")
            raw = p.read_bytes()
            cols = []
            if show_l:
                cols.append(f"{len(txt.splitlines()):6d}")
            if show_w:
                cols.append(f"{len(txt.split()):6d}")
            if show_c:
                cols.append(f"{len(raw):6d}")
            ctx.out(" ".join(cols) + f"  {f}")


def handle_grep(ctx: ShellContext, args: list[str]) -> None:
    ic = "-i" in args
    sn = "-n" in args
    rest = [a for a in args if not a.startswith("-")]
    if len(rest) < 2:
        ctx.fail("grep: [-in] <pattern> <file...>")
        return
    pat, files = rest[0], rest[1:]
    flags = re.IGNORECASE if ic else 0
    for f in files:
        p = resolve_target(ctx.cwd, f)
        if not p.is_file():
            ctx.fail(f"grep: {f}: ファイルではありません")
            continue
        for idx, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(pat, ln, flags):
                prefix = f"{f}:{idx}:" if sn else f"{f}:"
                ctx.out(f"{prefix}{ln}")


def handle_sort(ctx: ShellContext, args: list[str]) -> None:
    numeric = "-n" in args
    unique = "-u" in args
    reverse = "-r" in args
    files = [a for a in args if not a.startswith("-")]
    if not files:
        ctx.fail("sort: [-nur] <file>")
        return
    p = resolve_target(ctx.cwd, files[0])
    if not p.is_file():
        ctx.fail(f"sort: {files[0]}: ファイルではありません")
        return
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if numeric:
        lines.sort(
            key=lambda s: int(m.group()) if (m := re.search(r"-?\d+", s)) else 0,
            reverse=reverse,
        )
    else:
        lines.sort(reverse=reverse)
    if unique:
        dedup: list[str] = []
        for ln in lines:
            if not dedup or dedup[-1] != ln:
                dedup.append(ln)
        lines = dedup
    for ln in lines:
        ctx.out(ln)


def handle_uniq(ctx: ShellContext, args: list[str]) -> None:
    count_mode = "-c" in args
    files = [a for a in args if not a.startswith("-")]
    if not files:
        ctx.fail("uniq: [-c] <file>")
        return
    p = resolve_target(ctx.cwd, files[0])
    if not p.is_file():
        ctx.fail(f"uniq: {files[0]}: ファイルではありません")
        return
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    grouped: list[tuple[int, str]] = []
    for ln in lines:
        if grouped and grouped[-1][1] == ln:
            grouped[-1] = (grouped[-1][0] + 1, ln)
        else:
            grouped.append((1, ln))
    for cnt, ln in grouped:
        ctx.out(f"{cnt:5d} {ln}" if count_mode else ln)


def handle_cut(ctx: ShellContext, args: list[str]) -> None:
    delim = "\t"
    fields_arg = None
    files: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "-d" and i + 1 < len(args):
            delim = args[i + 1]
            i += 2
        elif args[i] == "-f" and i + 1 < len(args):
            fields_arg = args[i + 1]
            i += 2
        else:
            files.append(args[i])
            i += 1
    if not fields_arg or not files:
        ctx.fail("cut: -d <区切り> -f <列番号 例:1,3> <file>")
        return
    idxs = [int(x) - 1 for x in fields_arg.split(",") if x.strip().isdigit() and int(x) > 0]
    p = resolve_target(ctx.cwd, files[0])
    if not p.is_file():
        ctx.fail(f"cut: {files[0]}: ファイルではありません")
        return
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        cols = ln.split(delim)
        picked = [cols[j] for j in idxs if j < len(cols)]
        ctx.out(delim.join(picked))


def handle_awk(ctx: ShellContext, args: list[str]) -> None:
    if len(args) < 2:
        ctx.fail("awk: '{print $1, $2}' <file>")
        return
    expr, fname = args[0], args[1]
    p = resolve_target(ctx.cwd, fname)
    if not p.is_file():
        ctx.fail(f"awk: {fname}: ファイルではありません")
        return
    m = re.search(r"print\s+(.+?)\s*\}?\s*$", expr)
    if not m:
        ctx.fail("awk: print 指定のみ対応しています（例: '{print $1, $3}'）")
        return
    tokens = [t.strip() for t in m.group(1).split(",")]
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        cols = ln.split()
        row: list[str] = []
        for tk in tokens:
            if tk == "$0":
                row.append(ln)
            elif tk.startswith("$") and tk[1:].isdigit():
                pos = int(tk[1:]) - 1
                row.append(cols[pos] if 0 <= pos < len(cols) else "")
            else:
                row.append(tk.strip("'\""))
        ctx.out(" ".join(row))


def handle_diff(ctx: ShellContext, args: list[str]) -> None:
    if len(args) < 2:
        ctx.fail("diff: <file1> <file2>")
        return
    p1 = resolve_target(ctx.cwd, args[0])
    p2 = resolve_target(ctx.cwd, args[1])
    if not p1.is_file() or not p2.is_file():
        ctx.fail("diff: 両方とも存在するファイルを指定してください")
        return
    l1 = p1.read_text(encoding="utf-8", errors="replace").splitlines()
    l2 = p2.read_text(encoding="utf-8", errors="replace").splitlines()
    diffs = 0
    for idx in range(max(len(l1), len(l2))):
        a = l1[idx] if idx < len(l1) else "<EOF>"
        b = l2[idx] if idx < len(l2) else "<EOF>"
        if a != b:
            diffs += 1
            ctx.out(f"--- {args[0]}:{idx + 1}: {a}")
            ctx.out(f"+++ {args[1]}:{idx + 1}: {b}")
    if diffs == 0:
        ctx.out("差分はありません。")


def handle_sha256sum(ctx: ShellContext, args: list[str]) -> None:
    if not args:
        ctx.fail("sha256sum: <file...>")
        return
    for f in args:
        p = resolve_target(ctx.cwd, f)
        if not p.is_file():
            ctx.fail(f"sha256sum: {f}: ファイルではありません")
        else:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            ctx.out(f"{digest}  {f}")


def handle_find(ctx: ShellContext, args: list[str]) -> None:
    name_pat = None
    start_s = "."
    i = 0
    while i < len(args):
        if args[i] == "-name" and i + 1 < len(args):
            name_pat = args[i + 1]
            i += 2
        else:
            start_s = args[i]
            i += 1
    root = resolve_target(ctx.cwd, start_s)
    if not root.exists():
        ctx.fail(f"find: {start_s}: 見つかりません")
        return
    for p in sorted(root.rglob("*")):
        if name_pat is None or re.fullmatch(name_pat.replace("*", ".*").replace("?", "."), p.name):
            ctx.out(to_virtual_path(p))


def handle_stat(ctx: ShellContext, args: list[str]) -> None:
    for t in (args or ["."]):
        p = resolve_target(ctx.cwd, t)
        if not p.exists():
            ctx.fail(f"stat: {t}: 見つかりません")
        else:
            st = p.stat()
            ctx.out(f"File: {to_virtual_path(p)} | Size: {st.st_size} | Mode: {oct(st.st_mode & 0o777)}")


def handle_whoami(ctx: ShellContext, args: list[str]) -> None:
    ctx.out(os.getenv("USER", "drilluser"))


def handle_id(ctx: ShellContext, args: list[str]) -> None:
    uid = os.geteuid() if hasattr(os, "geteuid") else 1000
    gid = os.getegid() if hasattr(os, "getegid") else 1000
    ctx.out(f"uid={uid}({os.getenv('USER', 'drilluser')}) gid={gid}")


def handle_uname(ctx: ShellContext, args: list[str]) -> None:
    ctx.out(platform.uname().system if "-a" not in args else " ".join(platform.uname()))


def handle_env(ctx: ShellContext, args: list[str]) -> None:
    for k, v in sorted(os.environ.items()):
        ctx.out(f"{k}={v}")


def handle_cmdlist(ctx: ShellContext, args: list[str]) -> None:
    if ctx.web_mode:
        ctx.out("100選コマンド一覧はターミナル外パネルで確認してください。")
        return
    kw = args[0].lower() if args else ""
    matched = [c for c in ALL_100_COMMANDS if not kw or kw in c.lower()]
    for idx, c in enumerate(matched, 1):
        ctx.out(f"{idx:3d}. {c:<12} - {COMMAND_CATALOG.get(c, '基礎コマンド')}")


COMMAND_HANDLERS: dict[str, Callable[[ShellContext, list[str]], None]] = {
    "help": handle_help,
    "pwd": handle_pwd,
    "cd": handle_cd,
    "ls": handle_ls,
    "tree": handle_tree,
    "touch": handle_touch,
    "mkdir": handle_mkdir,
    "cp": handle_cp,
    "mv": handle_mv,
    "rm": handle_rm,
    "chmod": handle_chmod,
    "echo": handle_echo,
    "cat": handle_cat,
    "head": handle_head,
    "tail": handle_tail,
    "wc": handle_wc,
    "grep": handle_grep,
    "sort": handle_sort,
    "uniq": handle_uniq,
    "cut": handle_cut,
    "awk": handle_awk,
    "diff": handle_diff,
    "sha256sum": handle_sha256sum,
    "find": handle_find,
    "stat": handle_stat,
    "whoami": handle_whoami,
    "id": handle_id,
    "uname": handle_uname,
    "env": handle_env,
    "cmdlist": handle_cmdlist,
}


def run_shell_command(raw_cmd: str, v_cwd: str, *, web_mode: bool = True) -> dict:
    ctx = ShellContext(to_real_cwd(v_cwd), web_mode=web_mode)

    try:
        parts = shlex.split(raw_cmd)
    except ValueError as e:
        return {"ok": False, "cwd": to_virtual_path(ctx.cwd), "output": f"構文エラー: {e}"}

    if not parts:
        return {"ok": False, "cwd": to_virtual_path(ctx.cwd), "output": ""}

    cmd, args = parts[0], parts[1:]
    handler = COMMAND_HANDLERS.get(cmd)

    try:
        if handler is not None:
            handler(ctx, args)
        elif cmd in ALL_100_COMMANDS:
            ctx.out(f"{cmd}: 100選リスト掲載コマンドです（演習サンドボックスでは未実装または制限対象）。")
        else:
            ctx.fail(f"{cmd}: コマンドが見つかりません（'help' を参照）")
    except ValueError as e:
        ctx.fail(f"[BLOCKED] {e}")
    except Exception as e:
        ctx.fail(f"[ERROR] {e}")

    return {"ok": ctx.ok, "cwd": to_virtual_path(ctx.cwd), "output": ctx.buf.getvalue().rstrip("\n")}


@c1_bp.route("/")
def c1_page():
    seed_sandbox_files()
    return render_template("C1.html")


@c1_bp.route("/api/exec", methods=["POST"])
def c1_exec():
    data = request.get_json(silent=True) or {}
    raw_cmd = str(data.get("command", "")).strip()
    v_cwd = str(data.get("cwd", "/"))
    if not raw_cmd:
        return jsonify({"ok": False, "cwd": v_cwd, "output": ""})
    result = run_shell_command(raw_cmd, v_cwd, web_mode=True)
    return jsonify(result)


def run_local_cli() -> int:
    seed_sandbox_files()
    v_cwd = "/"
    print("C1 Local Drill Shell 起動（'help' または 'exit' で終了）")
    while True:
        try:
            line = input(f"c1:{v_cwd}$ ")
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            return 0

        raw = line.strip()
        if not raw:
            continue
        if raw in ("exit", "quit"):
            return 0
        if raw == "clear":
            os.system("clear" if os.name != "nt" else "cls")
            continue

        res = run_shell_command(raw, v_cwd, web_mode=False)
        v_cwd = res.get("cwd", v_cwd)
        if res.get("output"):
            print(res["output"])


if __name__ == "__main__":
    sys.exit(run_local_cli())