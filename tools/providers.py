"""Nhà cung cấp AI cho nhân viên ResearchLab.

Thêm loại mới: khai báo trong PRESETS, rồi viết nhánh tương ứng trong cli_argv() hoặc dùng "openai-api".
"""
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request

PRESETS = {
    "gemini-cli": {
        "label": "Gemini CLI (Google)", "kind": "cli", "bin": "gemini",
        "install": "npm install -g @google/gemini-cli", "login": "gemini", "key_env": "GEMINI_API_KEY",
        "login_hint": "Cửa sổ terminal sẽ mở: chọn Sign in with Google, đăng nhập trên trình duyệt, xong gõ /quit.",
    },
    "codex-cli": {
        "label": "ChatGPT / Codex CLI (OpenAI)", "kind": "cli", "bin": "codex",
        "install": "npm install -g @openai/codex", "login": "codex login", "key_env": "OPENAI_API_KEY",
        "login_hint": "Cửa sổ terminal sẽ mở và chuyển sang trình duyệt để đăng nhập tài khoản ChatGPT.",
    },
    "claude-cli": {
        "label": "Claude Code (Anthropic)", "kind": "cli", "bin": "claude",
        "install": "npm install -g @anthropic-ai/claude-code", "login": "claude", "key_env": "ANTHROPIC_API_KEY",
        "login_hint": "Cửa sổ terminal sẽ mở: gõ /login nếu được hỏi, xong gõ /exit.",
    },
    "antigravity-cli": {
        "label": "Antigravity CLI (Google)", "kind": "cli", "bin": "agy",
        "install": "winget install -e --id Google.AntigravityCLI", "login": "agy",
        "login_hint": "Cửa sổ terminal sẽ mở: đăng nhập Google trên trình duyệt (trang antigravity.google), xong gõ /exit.",
    },
    "gemini-api": {
        "label": "Gemini API (key từ Google AI Studio)", "kind": "api",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "login_hint": "Lấy key ở aistudio.google.com/apikey (đăng nhập Google, bấm Create API key), rồi bấm 🗝️ Nhập API key.",
    },
    "openai-api": {
        "label": "API kiểu OpenAI (MiMo, DeepSeek, OpenRouter, Ollama…)", "kind": "api",
        "login_hint": "Điền địa chỉ API, tên model và API key của nhà cung cấp.",
    },
    "manual": {
        "label": "Tự báo cáo (app khác)", "kind": "manual",
        "login_hint": "Nhân viên này làm trong app riêng và tự chấm công bằng office.py (xem AGENTS.md).",
    },
}

MODEL_HINTS = {  # gợi ý; để trống = model mặc định của CLI. Gõ tên khác vẫn được.
    "gemini-cli": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    "gemini-api": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    "codex-cli": ["gpt-5", "gpt-5-codex", "o3", "o4-mini"],
    "claude-cli": ["opus", "sonnet", "haiku", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"],
}

OK_PROMPT = "Trả lời đúng một chữ: OK"


def list_models(provider, secret):
    """Danh sách model: CLI dùng gợi ý sẵn, API kiểu OpenAI thì hỏi thẳng máy chủ (/models)."""
    t = provider.get("type")
    if t == "antigravity-cli":  # danh sách model lấy thẳng từ CLI
        exe = find_bin("agy")
        if not exe:
            raise RuntimeError("Chưa cài Antigravity CLI")
        r = subprocess.run([exe, "models"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            raise RuntimeError(explain(out.strip()))
        return [ln.split()[0] for ln in out.splitlines()  # dòng dạng "<id>\t<tên hiển thị>"
                if ln.strip() and not ln.lower().startswith(("fetching", "available", "error"))]
    if PRESETS.get(t, {}).get("kind") != "api":
        return MODEL_HINTS.get(t, [])
    base = api_base(provider)
    if not base:
        raise RuntimeError("Điền địa chỉ API trước")
    req = urllib.request.Request(base + "/models")
    if secret.get("api_key"):
        req.add_header("Authorization", "Bearer " + secret["api_key"])
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(explain(f"HTTP {e.code}")) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Không kết nối được {base}: {e.reason}") from e
    return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))
AUTH_WORDS = ("auth", "login", "log in", "credential", "sign in", "api key", "unauthorized", "401", "403")


def ensure_path():
    """Server có thể mở trước khi cài Node/CLI nên PATH cũ; bổ sung đường dẫn mặc định."""
    extra = [os.path.join(os.environ.get("APPDATA", ""), "npm"), r"C:\Program Files\nodejs"]
    path = os.environ.get("PATH", "")
    missing = [d for d in extra if d and d.lower() not in path.lower()]
    if missing:
        os.environ["PATH"] = os.pathsep.join([*missing, path])


def find_bin(name):
    ensure_path()
    found = shutil.which(name + ".cmd") or shutil.which(name)
    if found:
        return found
    # Mở từ shortcut/Explorer có thể mang PATH cũ (trước khi cài Node): dò thẳng các chỗ cài mặc định
    for d in (os.path.join(os.environ.get("APPDATA", ""), "npm"), os.path.expanduser(r"~\AppData\Roaming\npm"),
              r"C:\Program Files\nodejs", os.path.expanduser(r"~\.local\bin"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")):
        for ext in (".cmd", ".exe", ""):
            p = os.path.join(d, name + ext)
            if d and os.path.isfile(p):
                return p
    import glob  # CLI cài bằng winget dạng portable
    hits = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages", "*", name + ".exe"))
    # CLI cài bằng npm từ TRONG app Claude (gói MSIX): Windows chuyển AppData\Roaming vào thư mục riêng của gói, nên
    # văn phòng mở bằng shortcut thấy %APPDATA%\npm trống (lỗi thật 2026-10-28: "Chưa cài Claude Code")
    for ext in (".cmd", ".exe"):
        hits = hits or glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "*", "LocalCache",
                                              "Roaming", "npm", name + ext))
    return hits[0] if hits else None


def installed(provider):
    p = PRESETS.get(provider.get("type"), {})
    if p.get("kind") == "cli":
        return bool(find_bin(p["bin"]))
    return True


def env_with_key(provider, secret):
    env = dict(os.environ)
    # Giới hạn 2 thread cho MỌI lệnh nhân viên chạy (RULES.md mục 4) đặt sẵn ở đây: nhân viên gõ `OMP_NUM_THREADS=2 python …`
    # thì lệnh không khớp luật cho phép Bash(python:*) và bị chặn (lỗi thật 2026-10-28, Bánh / Kem / Su)
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env.setdefault(k, "2")
    key_env = PRESETS.get(provider.get("type"), {}).get("key_env")
    if key_env and secret.get("api_key"):
        env[key_env] = secret["api_key"]
    return env


TOOL_LOG = None  # đặt = [] để ghi lại TOÀN BỘ (tên công cụ, tham số) của lượt chạy (tester.py soát nhìn trộm lời giải)


def cli_argv(provider, instr, dirs, write=False, prompt_file=None, allow_cmds=False, allowed_tools=(), web=False,
             denied_tools=()):
    """write=True chỉ dùng khi sếp đã duyệt qua Thư ký.

    Trả về (argv, cách đưa nội dung): "stdin" = nội dung qua stdin, "stdin_all" = cả hướng dẫn lẫn nội dung
    qua stdin, "file" = nội dung nằm trong prompt_file để CLI tự đọc.
    """
    t, model = provider["type"], provider.get("model", "").strip()
    exe = find_bin(PRESETS[t]["bin"])
    if not exe:
        raise RuntimeError(f"Chưa cài {PRESETS[t]['label']} (bấm 'Cài đặt' trong hồ sơ nhân viên)")
    if t == "gemini-cli":
        mode = ("yolo" if allow_cmds else "auto_edit") if write else "plan"
        argv = [exe, "--approval-mode", mode, "--skip-trust", "-o", "text", "-p", " ".join(instr.split())]
        for d in dirs:
            argv += ["--include-directories", d]
        if model:
            argv += ["-m", model]
        return argv, "stdin"
    if t == "codex-cli":
        argv = [exe, "exec", "--sandbox", "workspace-write" if write else "read-only", "--skip-git-repo-check"]
        if model:
            argv += ["-m", model]
        return argv + ["-"], "stdin_all"
    if t == "claude-cli":
        # KHÔNG đưa lời dặn qua tham số: claude.cmd chạy qua cmd.exe, cmd cắt tham số ở chỗ xuống dòng làm mất các
        # tuỳ chọn phía sau (mất cả --output-format). Lời dặn + nội dung đi qua stdin (-p không kèm chữ).
        argv = [exe, "-p", "--permission-mode", "acceptEdits" if write else "plan",
                "--output-format", "stream-json", "--verbose", "--include-partial-messages"]
        # Gọn nhẹ: chỉ cấp công cụ cần cho việc, bỏ skill/MCP/cấu hình riêng của Claude Code trên máy.
        # Danh sách công cụ là phần nặng nhất (~47K → ~7.6K token mỗi lần gọi khi chỉ cấp công cụ đọc).
        tools = ["Read", "Glob", "Grep"] + (["Edit", "Write"] if write else []) + (["Bash"] if write and allow_cmds else []) \
            + (["WebSearch", "WebFetch"] if web else [])  # phòng được tra web (vd. Phòng Kỹ năng tìm skill có sẵn)
        argv += ["--tools", ",".join(tools), "--disable-slash-commands", "--strict-mcp-config",
                 "--setting-sources", "project", "--exclude-dynamic-system-prompt-sections"]
        allow = ([*allowed_tools] if write else []) + (["WebSearch", "WebFetch"] if web else [])
        if allow:  # lệnh phòng cho phép (vd. Bash(ssh:*)) chỉ khi sếp đã duyệt; tra web thì cho luôn (chỉ đọc)
            argv += ["--allowedTools", *allow]
        if denied_tools:  # luật cấm thắng luật cho phép (vd. Mò không được đọc thư mục lời giải)
            argv += ["--disallowedTools", *denied_tools]
        for d in dirs:
            argv += ["--add-dir", d]
        if model:
            argv += ["--model", model]
        return argv, "stdin_all"
    if t == "antigravity-cli":
        if prompt_file is None:
            return None, "file"
        if prompt_file.startswith("inline:"):  # nội dung ngắn: đưa thẳng vào câu lệnh
            prompt, extra = f"{instr}\n\n{prompt_file[7:]}".strip(), []
        else:  # tài liệu dài: agent đọc file bằng công cụ đọc file (không chạy lệnh shell)
            prompt = (f"{instr}\n\nThư giao việc và tài liệu kèm theo nằm trong file: {prompt_file}\n"
                      "Dùng công cụ đọc file (không dùng lệnh terminal) để đọc kỹ file đó rồi làm. "
                      "Trả lời bằng tiếng Việt, dạng Markdown.")
            extra = [os.path.dirname(prompt_file)]
        mode = ("auto" if allow_cmds else "accept-edits") if write else "plan"
        # KHÔNG dùng --disable-slash-commands với agy: nó làm --mode plan mất tác dụng (agy tự cảnh báo), khiến
        # agent chạy chế độ thường → mọi thao tác cần xin phép (kể cả đọc file) bị tự chặn khi chạy nền.
        argv = [exe, "-p", prompt, "--mode", mode, "--output-format", "stream-json"]
        for d in [*dirs, *extra]:
            argv += ["--add-dir", d]
        if model:
            argv += ["--model", model]
        return argv, "file"
    raise RuntimeError(f"Không biết chạy loại '{t}'")


QUOTA_WORDS = ("quota", "rate limit", "rate_limit", "ratelimit", "429", "resource_exhausted", "resource exhausted",
               "usage limit", "limit reached", "limit exceeded", "too many requests", "insufficient_quota",
               "credit balance", "out of credits", "exceeded your current")


class QuotaError(RuntimeError):
    """Hết token / quota: nhân viên đi ngủ tới khi được reset."""

    def __init__(self, msg, retry_after=3600):
        super().__init__(msg)
        self.retry_after = retry_after


def _retry_seconds(err):
    m = re.search(r"(?:retry|try again|reset|resets|available)[^0-9]{0,30}(\d+(?:\.\d+)?)\s*(ms|s|sec|second|m|min|minute|h|hr|hour)", err, re.I)
    if not m:
        return 3600
    n, unit = float(m.group(1)), m.group(2).lower()
    sec = n / 1000 if unit == "ms" else n * 3600 if unit.startswith("h") else n * 60 if unit.startswith("m") else n
    return int(min(max(sec, 60), 24 * 3600))


def raise_for(err):
    low = err.lower()
    if any(w in low for w in QUOTA_WORDS):
        raise QuotaError(f"Hết token / quota: {err[-200:]}", _retry_seconds(err))
    raise RuntimeError(explain(err))


class Reply(str):
    """Câu trả lời của model kèm số token: usage = {model: {in, out, cache, cost}}."""
    usage = None


def _reply(text, usage):
    r = Reply(text)
    r.usage = usage
    return r


def _short(p):
    p = str(p or "").replace("\\", "/").rstrip("/")
    return p.split("/")[-1] or p


def describe_tool(name, args):
    """Tên công cụ + tham số → câu tiếng Việt dễ hiểu cho sếp xem."""
    n, a = (name or "").lower(), args or {}
    path = a.get("file_path") or a.get("path") or a.get("Path") or a.get("AbsolutePath") or a.get("TargetFile") or ""
    pat = a.get("pattern") or a.get("Query") or a.get("query") or a.get("SearchPath") or ""
    cmd = a.get("command") or a.get("CommandLine") or ""
    if "read" in n or "view" in n:
        return f"📖 Đọc {_short(path) or 'file'}"
    if "grep" in n or "search" in n:
        return f"🔍 Tìm '{str(pat)[:40]}'" if pat else "🔍 Tìm trong file"
    if "glob" in n or "list" in n or "find" in n:
        return f"🗂️ Xem danh sách file {str(pat)[:30] or _short(path)}".strip()
    if "edit" in n or "replace" in n:
        return f"✍️ Sửa {_short(path) or 'file'}"
    if "write" in n or "create" in n:
        return f"📝 Ghi {_short(path) or 'file'}"
    if "bash" in n or "command" in n or "shell" in n:
        return f"⚙️ Chạy lệnh: {str(cmd)[:50]}"
    if "browser" in n:
        return "🌐 Dùng trình duyệt"
    if "web" in n or "fetch" in n:
        return f"🌐 Đọc web {str(a.get('url', ''))[:50]}"
    return f"🛠️ {name}"


def _stream(argv, stdin, cwd, env, timeout, t, on_step=None, on_rate=None, on_text=None, on_start=None):
    """Chạy CLI ở chế độ luồng sự kiện: báo từng thao tác (on_step) và hạn mức thật (on_rate).
    Trả về (mã thoát, dòng JSON kết quả cuối kiểu --output-format json, stderr)."""
    import threading
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", cwd=cwd, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    def kill_tree():
        """Hết giờ: diệt cả cây tiến trình. Chỉ diệt claude.exe thì bash/python con vẫn giữ luồng ra,
        app đứng chờ mãi (lỗi đã gặp: Mò chạy quá 2 phút)."""
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.kill()
            proc.stdout.close()  # nhả vòng đọc dù còn tiến trình cháu giữ ống
        except Exception:  # noqa: BLE001
            pass
    timed_out = []

    def on_timeout():
        timed_out.append(1)
        kill_tree()
    timer = threading.Timer(timeout, on_timeout)
    timer.start()
    if on_start:
        on_start(proc)
    err_buf = []
    threading.Thread(target=lambda: err_buf.append(proc.stderr.read()), daemon=True).start()

    def feed():
        try:
            proc.stdin.write(stdin or "")
            proc.stdin.close()
        except OSError:
            pass
    threading.Thread(target=feed, daemon=True).start()
    step = lambda s: on_step and on_step(s)  # noqa: E731
    import time as _t
    live = {"buf": "", "last": 0.0, "kind": ""}

    def think(delta, kind):
        """Gom chữ đang sinh ra, báo cho app tối đa ~1 lần/giây (đuôi 240 ký tự)."""
        if not on_text or not delta:
            return
        if kind != live["kind"]:
            live.update(buf="", kind=kind)
        live["buf"] = (live["buf"] + delta)[-240:]
        if _t.time() - live["last"] > 1.0:
            live["last"] = _t.time()
            on_text(live["buf"], kind)
    final, texts, usage = None, {}, {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0}
    status = "SUCCESS"
    try:
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if t == "claude-cli":
                typ = ev.get("type")
                if typ == "stream_event":
                    d = (ev.get("event") or {}).get("delta") or {}
                    if d.get("type") == "thinking_delta":
                        think(d.get("thinking", ""), "think")
                    elif d.get("type") == "text_delta":
                        think(d.get("text", ""), "say")
                    continue
                if typ == "assistant":
                    for c in ev.get("message", {}).get("content", []):
                        if c.get("type") == "tool_use":
                            step(describe_tool(c.get("name"), c.get("input")))
                            if TOOL_LOG is not None:
                                TOOL_LOG.append((c.get("name"), json.dumps(c.get("input"), ensure_ascii=False)))
                        elif c.get("type") == "text" and c.get("text", "").strip():
                            step("💬 Đang viết trả lời…")
                elif typ == "rate_limit_event" and on_rate:
                    on_rate(ev.get("rate_limit_info") or {})
                elif "result" in ev and ("usage" in ev or typ == "result"):
                    final = line
            else:  # antigravity-cli
                if ev.get("event") == "step_update":
                    su = ev.get("step_update", {})
                    if su.get("step_type") == "tool" and su.get("state") == "ACTIVE":
                        ti = su.get("tool_info") or {}
                        step(describe_tool(su.get("tool_name") or ti.get("name"), ti.get("parameters")))
                        if TOOL_LOG is not None:
                            TOOL_LOG.append((su.get("tool_name") or ti.get("name"), json.dumps(ti.get("parameters"), ensure_ascii=False)))
                    elif su.get("step_type") == "agent_response":
                        if su.get("thinking_delta"):
                            think(su["thinking_delta"], "think")
                        if su.get("text_delta"):
                            think(su["text_delta"], "say")
                            texts[su.get("step_index", 0)] = texts.get(su.get("step_index", 0), "") + su["text_delta"]
                            if len(texts[su.get("step_index", 0)]) < 40:
                                step("💬 Đang viết trả lời…")
                        if su.get("state") == "DONE":
                            for k, v in (su.get("usage") or {}).items():
                                if k in usage and isinstance(v, (int, float)):
                                    usage[k] += v
                        if su.get("state") in ("ERROR", "FAILED"):
                            status = "ERROR"
                elif ev.get("response") is not None:  # sự kiện kết quả cuối (nếu CLI có gửi)
                    final = line
                elif ev.get("event") in ("error", "result") and ev.get("error"):
                    status = "ERROR"
                    texts[10**9] = str(ev.get("error"))
        proc.wait()
        if on_text and live["buf"]:
            on_text(live["buf"], live["kind"])
    finally:
        timer.cancel()
    if timed_out:  # nói rõ là hết giờ, để văn phòng phân loại lỗi (không thử lại mù)
        raise RuntimeError(f"Hết giờ: lượt chạy quá {timeout} giây nên đã bị dừng")
    if t != "claude-cli" and final is None:
        answer = texts[max(texts)] if texts else ""
        final = json.dumps({"status": status, "response": answer, "usage": {**usage,
                            "output_tokens": usage["output_tokens"]}}, ensure_ascii=False)
    return proc.returncode, final or "", "".join(err_buf)


def _parse_cli_json(t, raw, provider):
    """Claude / Antigravity chạy --output-format json: tách câu trả lời và số token thật."""
    try:
        d = json.loads(raw.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    if t == "claude-cli":
        if d.get("is_error"):
            raise_for(str(d.get("result") or d.get("api_error_status") or "lỗi"))
        usage = {m: {"in": u.get("inputTokens", 0), "out": u.get("outputTokens", 0),
                     "cache": u.get("cacheReadInputTokens", 0) + u.get("cacheCreationInputTokens", 0),
                     "cost": u.get("costUSD", 0.0)} for m, u in (d.get("modelUsage") or {}).items()}
        return _reply(d.get("result", ""), usage)
    if t == "antigravity-cli":
        if str(d.get("status", "")).upper() not in ("SUCCESS", ""):
            raise_for(str(d.get("error") or d.get("response") or d.get("status")))
        u = d.get("usage") or {}
        model = provider.get("model") or "antigravity (mặc định)"
        return _reply(d.get("response", ""), {model: {"in": u.get("input_tokens", 0),
                                                      "out": u.get("output_tokens", 0) + u.get("thinking_tokens", 0),
                                                      "cache": u.get("cache_read_tokens", 0), "cost": 0.0}})
    return None


def api_base(provider):
    """Địa chỉ API: lấy của nhân viên, để trống thì dùng địa chỉ mặc định của loại (vd. Gemini API)."""
    return (provider.get("base_url") or PRESETS.get(provider.get("type"), {}).get("base_url", "")).rstrip("/")


def explain(err):
    low = err.lower()
    if "ineligibletier" in low or "no longer supported" in low:
        # Không dùng chữ "đăng nhập" để Thư ký không hỏi sếp đăng nhập lại (đăng nhập không giải quyết được)
        return ("Google không còn cho Gemini CLI dùng tài khoản Google cá nhân. "
                "Đổi nhà cung cấp sang 'Gemini API' và nhập API key từ aistudio.google.com/apikey")
    if any(w in low for w in AUTH_WORDS):
        return "Chưa đăng nhập hoặc API key sai (bấm 'Đăng nhập' trong hồ sơ nhân viên)"
    return err[-300:]


def _system_file(text):
    """Ghi phần cố định ra file đặt tên theo nội dung: cùng nội dung → cùng file → Claude đọc lại từ cache."""
    import hashlib
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "researchlab-prompts")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, hashlib.sha1(text.encode("utf-8")).hexdigest()[:16] + ".md")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return path


def run(provider, secret, instr, content, dirs=(), cwd=None, timeout=1800, write=False, allow_cmds=False,
        allowed_tools=(), system="", on_step=None, on_rate=None, on_text=None, on_start=None, web=False, denied_tools=()):
    kind = PRESETS.get(provider.get("type"), {}).get("kind")
    if system and provider.get("type") != "claude-cli" and kind != "api":
        content = f"{system}\n\n{content}"  # CLI khác không có ô system prompt: đặt phần cố định lên đầu
    if kind == "cli":
        perms = {"allow_cmds": allow_cmds and write, "allowed_tools": tuple(allowed_tools) if write else (), "web": bool(web)}
        if denied_tools and provider.get("type") == "claude-cli":
            perms["denied_tools"] = tuple(denied_tools)
        argv, how = cli_argv(provider, instr, dirs, write, **perms)
        if system and provider.get("type") == "claude-cli":
            argv += ["--append-system-prompt-file", _system_file(system)]
        tmpdir = None
        if how == "file" and len(content or "") <= 20000:  # CLI không đọc stdin: nội dung ngắn đưa thẳng vào lệnh
            argv, how = cli_argv(provider, instr, dirs, write, prompt_file="inline:" + (content or ""), **perms)
        elif how == "file":  # dài: ghi ra file tạm trong thư mục làm việc cho agent tự đọc
            import tempfile
            tmpdir = tempfile.mkdtemp(prefix=".researchlab-", dir=cwd if cwd and os.path.isdir(cwd) else None)
            pf = os.path.join(tmpdir, "thu-giao-viec.md")
            with open(pf, "w", encoding="utf-8") as f:
                f.write(content)
            argv, how = cli_argv(provider, instr, dirs, write, prompt_file=pf, **perms)
        stdin = {"stdin": content, "stdin_all": f"{instr}\n\n{content}"}.get(how, "")
        try:
            if provider["type"] in ("claude-cli", "antigravity-cli"):  # luồng sự kiện: biết từng thao tác
                code, out, err = _stream(argv, stdin, cwd, env_with_key(provider, secret), timeout, provider["type"],
                                         on_step, on_rate, on_text, on_start)
                r = subprocess.CompletedProcess(argv, code, out, err)
            else:
                r = subprocess.run(argv, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   cwd=cwd, timeout=timeout, env=env_with_key(provider, secret),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # không bật cửa sổ đen
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise_for((r.stderr or r.stdout).strip() or f"thoát với mã {r.returncode}")
        parsed = _parse_cli_json(provider["type"], r.stdout, provider)
        if parsed is not None:
            if not parsed.strip():
                raise_for((r.stderr or "").strip() or "không có câu trả lời")
            return parsed
        est = (len(stdin or "") + sum(len(a) for a in argv)) // 4  # CLI không báo token: ước lượng ~4 ký tự/token
        return _reply(r.stdout, {(provider.get("model") or provider["type"]) + " (ước tính)":
                                 {"in": est, "out": len(r.stdout) // 4, "cache": 0, "cost": 0.0}})
    if kind == "api":
        base, model = api_base(provider), provider.get("model", "")
        if not base or not model:
            raise RuntimeError("Thiếu địa chỉ API hoặc tên model")
        body = json.dumps({"model": model, "messages": [  # phần cố định ở đầu system: nhà cung cấp tự cache
            {"role": "system", "content": f"{system}\n\n{instr}" if system else instr},
            {"role": "user", "content": content}]}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if secret.get("api_key"):
            headers["Authorization"] = "Bearer " + secret["api_key"]
        req = urllib.request.Request(base + "/chat/completions", data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            retry = e.headers.get("Retry-After", "")
            raise_for(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}" + (f" retry after {retry} s" if retry.isdigit() else ""))
        except urllib.error.URLError as e:
            raise RuntimeError(f"Không kết nối được {base}: {e.reason}") from e
        u = data.get("usage") or {}
        return _reply(data["choices"][0]["message"]["content"],
                      {data.get("model") or model: {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0),
                                                    "cache": 0, "cost": 0.0}})
    raise RuntimeError("Nhân viên này tự báo cáo, không nhận việc tự động")


def check(provider, secret):
    return run(provider, secret, OK_PROMPT, "", timeout=180)  # Reply: .strip() khi cần chữ, .usage là token


def open_terminal(title, command, provider=None, secret=None):
    """Mở một cửa sổ terminal mới trên máy để người dùng tương tác (đăng nhập, cài đặt)."""
    ensure_path()
    env = env_with_key(provider, secret or {}) if provider else dict(os.environ)
    subprocess.Popen(f'start "{title}" cmd /k "chcp 65001 >nul & {command}"', shell=True, env=env)


def login(provider, name):
    p = PRESETS.get(provider.get("type"), {})
    if p.get("kind") != "cli":
        raise RuntimeError("Loại này đăng nhập bằng API key, không cần mở terminal")
    if not find_bin(p["bin"]):
        raise RuntimeError("Chưa cài, bấm 'Cài đặt' trước")
    exe = find_bin(p["bin"])  # đường dẫn đầy đủ: terminal mới có thể mang PATH cũ
    rest = p["login"].split(" ", 1)[1] if " " in p["login"] else ""
    open_terminal(f"Dang nhap {name}", f'"{exe}" {rest}'.strip())


def install(provider, name):
    p = PRESETS.get(provider.get("type"), {})
    if not p.get("install"):
        raise RuntimeError("Loại này không cần cài")
    tool = p["install"].split()[0]
    if not (find_bin(tool) or shutil.which(tool)):
        raise RuntimeError("Chưa có Node.js/npm trên máy" if tool == "npm" else f"Máy chưa có {tool}")
    open_terminal(f"Cai {name}", f'{p["install"]} && echo. && echo Xong! Dong cua so nay roi bam Kiem tra ket noi.')
