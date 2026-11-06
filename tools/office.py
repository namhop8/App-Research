"""ResearchLab office: chấm công cho nhân viên AI + server cho app quản lý.

Chỉ dùng thư viện chuẩn của Python.

    python office.py status claude working "Chạy thí nghiệm EXP-3"
    python office.py log gemini "Đọc xong 12 bài về alert ranking"
    python office.py task add "Cài baseline XGBoost" --owner antigravity --phase experiment
    python office.py task move 3 doing
    python office.py mail claude gemini review "Review Section 4" --input D:/Paper3/P3/main.tex
    python office.py serve            # mở http://localhost:8765, nhân viên tự nhận thư
"""
import argparse
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import providers  # noqa: E402
import sysmon  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "office.json"
SECRETS = ROOT / "state" / "secrets.json"
ACTIVITY = ROOT / "state" / "activity.jsonl"
INBOX = ROOT / "inbox"
APP = ROOT / "app"
SKILLS = ROOT / "skills"  # mỗi kỹ năng: skills/<tên>/SKILL.md (frontmatter name, description)

STATUSES = ("working", "idle", "waiting", "error", "off")
COLUMNS = ("todo", "doing", "review", "done")
PHASES = ("idea", "lit", "design", "experiment", "results", "writing", "review", "code", "deploy", "security", "skill", "ctf")
MAIL_KINDS = ("task", "lit", "review", "code", "assign", "approve")
HATS = ("sparkle", "headphones", "propeller", "cap", "headset", "antenna", "glasses", "none")
OLD_HATS = {"twins": "headphones", "bow": "headset"}  # văn phòng toàn con trai: đổi phụ kiện cũ

DEFAULT_DEPTS = {
    "reception": {"name": "Quầy lễ tân", "icon": "🛎️", "order": 0, "system": True},
    # sếp vào đây cấp quyền: việc đang chờ quyền + quyền thường trực của từng nhân viên + thư mục từng phòng
    "quyen": {"name": "Phòng Cấp quyền", "icon": "🔐", "order": 0, "system": True, "kind": "perms"},
    # Thư mục làm việc tương đối được tính từ thư mục gốc của app, nên mang app sang máy khác vẫn chạy
    "research": {"name": "Phòng Nghiên cứu", "icon": "🔬", "order": 1, "workdir": "projects",
                 "notes": "Tuân thủ RULES.md: thí nghiệm trước, số liệu sinh tự động, chỉ trích dẫn Q1/A*."},
    "skills": {"name": "Phòng Kỹ năng", "icon": "🧰", "order": 9, "workdir": "skills",
               "notes": ("Viết kỹ năng (skill) cho các phòng khác. Mỗi kỹ năng là một thư mục skills/<ten-khong-dau>/ "
                         "có file SKILL.md: phần đầu YAML gồm name và description (1-2 câu: dùng khi nào), "
                         "phần thân là hướng dẫn từng bước, ví dụ, lệnh mẫu, lỗi hay gặp. Ngắn gọn, làm được ngay. "
                         "Không đưa mật khẩu, khoá, token vào kỹ năng.")},
    "web": {"name": "Phòng Web & Deploy", "icon": "🌐", "order": 2, "workdir": "",
            "notes": "Code web, test trước khi deploy. Mọi lệnh deploy/push/ssh phải được sếp duyệt qua Thư ký."},
}
SECRETARY = "thuky"
DEPUTY = "phosep"
DEFAULT_AGENTS = {
    DEPUTY: {"name": "Phó sếp", "title": "Giữ lệnh thường trực của sếp", "dept": "reception", "color": "#b39ddb",
             "hat": "cap", "plant": "📜", "provider": {"type": "manual"}, "auto": False, "system": True},
    SECRETARY: {"name": "Tèo", "title": "Thư ký · xin sếp duyệt", "dept": "reception", "color": "#6cc3d5",
                "hat": "headset", "plant": "☎️", "provider": {"type": "manual"}, "auto": False, "system": True},
    "claude": {"name": "Claude", "title": "Trưởng nhóm", "dept": "research", "color": "#f29f72", "hat": "sparkle",
               "plant": "🌻", "provider": {"type": "claude-cli"}, "auto": True},
    "gemini": {"name": "Gemini", "title": "Thủ thư & Reviewer 2", "dept": "research", "color": "#8ea7f2", "hat": "headphones",
               "plant": "📚", "provider": {"type": "gemini-cli"}, "auto": True},
    "antigravity": {"name": "Antigravity", "title": "Kỹ sư", "dept": "research", "color": "#7fcfa8", "hat": "propeller",
                    "plant": "🔧", "provider": {"type": "manual"}, "auto": False},
}
AGENT_BLANK = {"status": "idle", "task": "", "since": 0, "dept": "research", "color": "#c9a7f2", "hat": "none",
               "plant": "🪴", "provider": {"type": "manual"}, "auto": False, "conn": {"ok": None, "msg": "", "t": 0}}

class _OfficeLock:
    """Khoá dùng chung giữa các luồng VÀ các tiến trình (server, CLI, hook) khi sửa office.json."""

    def __init__(self):
        self.r = threading.RLock()
        self.depth = 0
        self.fd = None

    def __enter__(self):
        self.r.acquire()
        self.depth += 1
        if self.depth == 1:
            try:
                path = STATE.parent / ".lock"
                path.parent.mkdir(parents=True, exist_ok=True)
                for _ in range(400):
                    try:
                        self.fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        break
                    except (FileExistsError, PermissionError):
                        # PermissionError: Windows báo khi file .lock đang bị xoá dở (tiến trình khác vừa nhả) -> chờ rồi thử lại.
                        try:
                            if time.time() - path.stat().st_mtime > 15:  # khoá mồ côi
                                path.unlink()
                        except OSError:
                            pass
                        time.sleep(0.05)
            except BaseException:
                # Lỗi bất ngờ khi lấy khoá file: trả lại khoá luồng, kẻo mọi lệnh ghi sau đó chờ mãi.
                self.depth -= 1
                self.fd = None
                self.r.release()
                raise
        return self

    def __exit__(self, *exc):
        self.depth -= 1
        if self.depth == 0 and self.fd is not None:
            os.close(self.fd)
            self.fd = None
            try:
                (STATE.parent / ".lock").unlink()
            except OSError:
                pass
        self.r.release()


_lock = _OfficeLock()


def now():
    return int(time.time())


def _retry(fn):
    for i in range(30):  # Windows: file có thể đang bị tiến trình khác mở
        try:
            return fn()
        except PermissionError:
            time.sleep(0.05 * (i + 1))
    return fn()


def load():
    s = _retry(lambda: json.loads(STATE.read_text(encoding="utf-8"))) if STATE.exists() else {"agents": {}, "tasks": [], "next_id": 1}
    s.setdefault("depts", {})
    s.setdefault("approvals", [])
    s.setdefault("policies", [])
    s.setdefault("next_policy", 1)
    if not s["depts"]:
        s["depts"] = json.loads(json.dumps(DEFAULT_DEPTS))
    for k, v in DEFAULT_DEPTS.items():
        if v.get("system"):
            s["depts"].setdefault(k, json.loads(json.dumps(v)))
    if not s["agents"]:
        s["agents"] = {k: {"status": "idle", "task": "", "since": 0} for k in DEFAULT_AGENTS}
    for sys_agent in (DEPUTY, SECRETARY):
        s["agents"].setdefault(sys_agent, {"status": "idle", "task": "", "since": 0})
    for k, a in s["agents"].items():  # bổ sung trường mới cho dữ liệu cũ
        base = {**json.loads(json.dumps(AGENT_BLANK)), **json.loads(json.dumps(DEFAULT_AGENTS.get(k, {})))}
        for f, v in base.items():
            a.setdefault(f, v)
        a["hat"] = OLD_HATS.get(a["hat"], a["hat"])
    sec = s["agents"][SECRETARY]
    if sec.get("name") == "Bé Thư":  # bản cũ là thư ký nữ
        sec.update(name="Tèo", color="#6cc3d5", plant="☎️")
    return s


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    _retry(lambda: os.replace(tmp, STATE))


def log(agent, text, kind="log", **extra):
    ACTIVITY.parent.mkdir(parents=True, exist_ok=True)
    with ACTIVITY.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now(), "agent": agent, "kind": kind, "text": text, **extra}, ensure_ascii=False) + "\n")


def recent_activity(n=200):
    if not ACTIVITY.exists():
        return []
    lines = ACTIVITY.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(x) for x in reversed(lines) if x.strip()]


def ascii_id(text):
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24]


# ---------- secrets (không bao giờ gửi ra app) ----------

def _secrets():
    return json.loads(SECRETS.read_text(encoding="utf-8")) if SECRETS.exists() else {}


def get_secret(agent_id):
    return _secrets().get(agent_id, {})


def set_secret(agent_id, api_key):
    with _lock:
        s = _secrets()
        if api_key:
            s[agent_id] = {"api_key": api_key}
        else:
            s.pop(agent_id, None)
        SECRETS.write_text(json.dumps(s, indent=2), encoding="utf-8")


# ---------- tasks / status / mail ----------

def set_status(agent, status, task=""):
    if status not in STATUSES:
        raise ValueError(f"Trạng thái phải là một trong: {', '.join(STATUSES)}")
    with _lock:
        s = load()
        if agent not in s["agents"]:
            raise ValueError(f"Không có nhân viên '{agent}'. Có: {', '.join(s['agents'])}")
        s["agents"][agent].update(status=status, task=task, since=now())
        if status != "off":
            s["agents"][agent].pop("sleep_until", None)  # đánh thức
        save(s)
    log(agent, f"[{status}] {task}" if task else f"[{status}]", kind="status")


def go_sleep(agent, seconds, reason=""):
    """Hết token: cho nhân viên đi ngủ tới khi quota reset."""
    until = now() + int(seconds)
    wake = datetime.fromtimestamp(until).strftime("%H:%M")
    with _lock:
        s = load()
        if agent not in s["agents"]:
            return
        s["agents"][agent].update(status="off", task=f"Hết token, ngủ tới {wake} 😴", since=now(), sleep_until=until)
        save(s)
    log(agent, f"Hết token rồi, đi ngủ tới {wake} 😴" + (f" ({reason[:120]})" if reason else ""), kind="sleep")


def wake_due():
    """Gọi định kỳ: ai ngủ đủ giấc thì dậy làm tiếp. Trả về danh sách vừa dậy."""
    woke = []
    with _lock:
        s = load()
        for k, a in s["agents"].items():
            if a.get("sleep_until") and a["sleep_until"] <= now():
                a.pop("sleep_until")
                a.update(status="idle", task="", since=now())
                woke.append(k)
        if woke:
            save(s)
    for k in woke:
        log(k, "Ngủ dậy rồi, làm tiếp thôi! ☀️", kind="sleep")
    return woke


def sleeping(agent):
    return (load()["agents"].get(agent, {}).get("sleep_until") or 0) > now()


_last_step = {}


def set_step(agent, text):
    """Thao tác nhân viên đang làm (đọc file, tìm, sửa…); giữ 15 thao tác gần nhất của việc hiện tại."""
    if not text or _last_step.get(agent) == text:
        return
    _last_step[agent] = text
    with _lock:
        s = load()
        a = s["agents"].get(agent)
        if a is None:
            return
        a["step"] = text
        a["steps"] = (a.get("steps", []) + [[now(), text]])[-15:]
        save(s)


def clear_steps(agent):
    _last_step.pop(agent, None)
    with _lock:
        s = load()
        if agent in s["agents"]:
            s["agents"][agent].update(step="", steps=[], thought="", thought_kind="")
            save(s)


def set_thought(agent, text, kind):
    """Chữ model đang nghĩ / đang viết (đuôi ~240 ký tự) cho bong bóng suy nghĩ trên đầu nhân vật."""
    with _lock:
        s = load()
        if agent in s["agents"]:
            s["agents"][agent].update(thought=" ".join(text.split())[-240:], thought_kind=kind, thought_t=now())
            save(s)


def set_rate(acc, info):
    """Hạn mức THẬT do Claude Code báo (loại five_hour / seven_day, trạng thái, giờ reset)."""
    if not info.get("rateLimitType"):
        return
    with _lock:
        s = load()
        r = s.setdefault("rates", {}).setdefault(acc, {})
        r[info["rateLimitType"]] = {"status": info.get("status", ""), "resets": int(info.get("resetsAt") or 0), "t": now()}
        for win, w in (info.get("unifiedWindows") or {}).items():  # mức dùng thật của cả tài khoản (0..1)
            r.setdefault(win, {}).update(util=float(w.get("utilization") or 0), resets=int(w.get("resetsAt") or 0), t=now())
        save(s)


def set_model_now(agent, model):
    """Model đang thật sự chạy (có thể khác model cài sẵn: duyệt dùng model nhẹ…), hiện trên kính nhân vật."""
    with _lock:
        s = load()
        if agent in s["agents"]:
            s["agents"][agent]["model_now"] = model or ""
            save(s)


def set_conn(agent, ok, msg=""):
    with _lock:
        s = load()
        if agent in s["agents"]:
            s["agents"][agent]["conn"] = {"ok": ok, "msg": msg[:200], "t": now()}
            save(s)


def add_task(title, owner="", phase="idea", actor=None):
    if phase not in PHASES:
        raise ValueError(f"Phase phải là một trong: {', '.join(PHASES)}")
    if not title.strip():
        raise ValueError("Thiếu tên việc")
    with _lock:
        s = load()
        t = {"id": s["next_id"], "title": title.strip(), "owner": owner, "phase": phase,
             "column": "todo", "created": now(), "updated": now()}
        s["tasks"].append(t)
        s["next_id"] += 1
        save(s)
    log(actor or owner or "boss", f"Tạo việc #{t['id']}: {t['title']}", kind="task")
    return t


# ---------- Thanh máu: hạn mức (quota) ước tính theo tài khoản ----------
# Các CLI không cho xem quota còn lại, nên văn phòng tự đếm số lần gọi model trong một khung giờ.
# Nhân viên dùng chung nhà cung cấp = dùng chung tài khoản = dùng chung một thanh máu.
QUOTA_DEFAULTS = {"claude-cli": {"window_h": 5, "limit": 40, "week": 300},
                  "antigravity-cli": {"window_h": 5, "limit": 40, "week": 300},
                  "codex-cli": {"window_h": 5, "limit": 40, "week": 300},
                  "gemini-cli": {"window_h": 24, "limit": 100, "week": 700},
                  "gemini-api": {"window_h": 24, "limit": 100, "week": 700},
                  "openai-api": {"window_h": 24, "limit": 200, "week": 1400}}
QUOTA_FALLBACK = {"window_h": 5, "limit": 40, "week": 300}  # nhà cung cấp mới chưa khai báo


def account_of(agent):
    t = agent.get("provider", {}).get("type", "manual")
    return None if providers.PRESETS.get(t, {}).get("kind") == "manual" else t


def record_use(agent_id, ok=True, usage=None):
    """Ghi một lần gọi model (sau mỗi việc / mỗi lần kiểm tra kết nối) + cộng token theo model."""
    with _lock:
        s = load()
        acc = account_of(s["agents"].get(agent_id, {}))
        if not acc:
            return
        day = datetime.now().strftime("%Y-%m-%d")
        for model, u in (usage or {}).items():
            for bucket in (s.setdefault("tokens", {}), s.setdefault("tokens_day", {}).setdefault(day, {})):
                m = bucket.setdefault(model, {"calls": 0, "in": 0, "out": 0, "cache": 0, "cost": 0.0, "acc": acc})
                m["calls"] += 1
                for k in ("in", "out", "cache"):
                    m[k] += int(u.get(k, 0) or 0)
                m["cost"] = round(m["cost"] + float(u.get("cost", 0) or 0), 6)
        s["tokens_day"] = dict(sorted(s.get("tokens_day", {}).items())[-30:])  # giữ 30 ngày
        u = s.setdefault("usage", {}).setdefault(acc, [])
        u.append([now(), agent_id, 1 if ok else 0])
        keep = now() - 8 * 86400  # giữ 8 ngày cho hạn mức tuần
        s["usage"][acc] = [x for x in u if x[0] >= keep][-5000:]
        save(s)


def set_quota(acc, window_h=None, limit=None, week=None):
    with _lock:
        s = load()
        q = s.setdefault("quotas", {}).setdefault(acc, dict(QUOTA_DEFAULTS.get(acc, QUOTA_FALLBACK)))
        if week is not None:
            q["week"] = max(1, int(week))
        if window_h is not None:
            q["window_h"] = max(0.5, min(168.0, float(window_h)))
        if limit is not None:
            q["limit"] = max(1, int(limit))
        save(s)
    return q


def quota_status(s):
    """Máu từng tài khoản: % còn lại, đã dùng/hạn mức, giờ hồi (giây tới khi hồi thêm)."""
    out = {}
    accounts = {account_of(a) for a in s["agents"].values()} - {None}
    for acc in accounts:
        q = {**QUOTA_FALLBACK, **QUOTA_DEFAULTS.get(acc, {}), **s.get("quotas", {}).get(acc, {})}
        win = q["window_h"] * 3600
        calls = sorted(x[0] for x in s.get("usage", {}).get(acc, []) if x[0] >= now() - win)
        week_calls = sorted(x[0] for x in s.get("usage", {}).get(acc, []) if x[0] >= now() - 7 * 86400)
        hp = max(0.0, 1 - len(calls) / q["limit"])
        sleepers = [a.get("sleep_until") or 0 for a in s["agents"].values() if account_of(a) == acc]
        sleep_until = max(sleepers + [0])
        if sleep_until > now():  # nhà cung cấp báo hết token thật
            hp, reset = 0.0, sleep_until - now()
        else:
            reset = int(calls[0] + win - now()) if calls else 0  # lúc lần gọi cũ nhất rời khung giờ
        week_hp = 0.0 if sleep_until > now() and hp == 0 and len(week_calls) >= q["week"] else max(0.0, 1 - len(week_calls) / q["week"])
        real = s.get("rates", {}).get(acc, {})
        five, week_r = real.get("five_hour", {}), real.get("seven_day", {})
        real_five = real_week = False
        if five.get("resets", 0) > now():  # giờ reset + mức dùng thật của cửa sổ 5 giờ
            reset = five["resets"] - now()
            if "util" in five:
                hp, real_five = max(0.0, 1 - five["util"]), True
            if five.get("status") == "rejected":
                hp = 0.0
        week_reset_real = week_r.get("resets", 0) - now() if week_r.get("resets", 0) > now() else 0
        if week_reset_real and "util" in week_r:
            week_hp, real_week = max(0.0, 1 - week_r["util"]), True
        if week_r.get("status") == "rejected":
            week_hp = 0.0
        out[acc] = {"hp": round(hp, 3), "used": len(calls), "limit": q["limit"], "window_h": q["window_h"],
                    "week_hp": round(week_hp, 3), "week_used": len(week_calls), "week": q["week"],
                    "week_reset": week_reset_real or (int(week_calls[0] + 7 * 86400 - now()) if week_calls else 0),
                    "real_five": real_five, "real_week": real_week,
                    "reset": max(0, reset), "exhausted": sleep_until > now(),
                    "label": providers.PRESETS.get(acc, {}).get("label", acc)}
    return out


# ---------- Phòng Kỹ năng ----------

SKILL_DEPT = "skills"
NEED_SKILL = re.compile(r"^\s*\[CẦN KỸ NĂNG\]\s*(.+)$", re.M)


def list_skills():
    """Kỹ năng có trong skills/: đọc name + description từ phần đầu SKILL.md."""
    out = []
    if not SKILLS.exists():
        return out
    for f in sorted(SKILLS.glob("*/SKILL.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        meta = {}
        m = re.match(r"---\s*\n(.*?)\n---", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
        phases = [x.strip() for x in str(meta.get("phases", "")).split(",") if x.strip()]
        desc = meta.get("description", "")
        if desc in ("|", ">", ""):  # mô tả nhiều dòng kiểu YAML
            m2 = re.search(r"description:\s*[|>]\s*\n((?:[ \t]+.*\n)+)", m.group(1) + "\n" if m else "")
            desc = " ".join(x.strip() for x in m2.group(1).splitlines()) if m2 else ""
        out.append({"id": f.parent.name, "name": meta.get("name", f.parent.name), "description": desc,
                    "phases": phases, "private": str(meta.get("private", "")).lower() == "true",
                    "path": str(f), "t": int(f.stat().st_mtime)})
    return out


def skill_maker():
    """Nhân viên của Phòng Kỹ năng (người đầu tiên trong phòng)."""
    return next((k for k, a in load()["agents"].items() if a["dept"] == SKILL_DEPT and not a.get("system")), None)


def request_skill(from_agent, need, dept_id):
    """Nhân viên thiếu kỹ năng: gửi thư nhờ Phòng Kỹ năng (chế độ ghi nên Thư ký sẽ xin sếp duyệt)."""
    maker = skill_maker()
    if not maker or maker == from_agent:
        return None
    key = re.sub(r"\W+", " ", need.lower()).split()[:6]  # vài chữ đầu của yêu cầu
    for t in load()["tasks"]:  # đã có người nhờ kỹ năng gần giống mà chưa xong thì không nhờ thêm
        if t["owner"] == maker and t["column"] != "done":
            words = set(re.sub(r"\W+", " ", t["title"].lower()).split())
            if key and sum(w in words for w in key) >= max(3, len(key) - 2):
                return None
    s = load()
    dname = s["depts"].get(dept_id, {}).get("name", dept_id)
    body = (f"{s['agents'].get(from_agent, {}).get('name', from_agent)} ({dname}) cần kỹ năng:\n{need}\n\n"
            f"Tạo kỹ năng mới trong skills/<ten-khong-dau>/SKILL.md theo đúng quy định của phòng. "
            f"Nếu đã có kỹ năng gần giống thì sửa/bổ sung kỹ năng đó.")
    return send_mail(from_agent, maker, "task", f"Kỹ năng cho {dname}: {need[:60]}", body, (), "", "write",
                     str(SKILLS), for_dept=dept_id)


def attach_skills(dept_id, skill_ids):
    with _lock:
        s = load()
        d = s["depts"].get(dept_id)
        if not d:
            return
        d["skills"] = sorted(set(d.get("skills", [])) | set(skill_ids))
        save(s)
    log(DEPUTY, f"Gắn kỹ năng {', '.join(skill_ids)} cho {d['name']} 🧰", kind="hr")


# ---------- Phó sếp phân việc ----------

PHASE_DEPT = {"lit": "research", "review": "research", "idea": "research", "design": "research",
              "experiment": "research", "results": "research", "writing": "research", "code": ("web", "clb"),
              "deploy": ("web", "clb"), "security": ("clb", "web"), "skill": "skills", "ctf": "clb"}
PHASE_ROLE = {"lit": ("thủ thư", "tài liệu"), "review": ("review",), "code": ("kỹ sư", "dev", "code"),
              "deploy": ("kỹ sư", "deploy", "devops"), "experiment": ("kỹ sư",), "idea": ("trưởng nhóm",),
              "design": ("trưởng nhóm",), "results": ("trưởng nhóm",), "writing": ("trưởng nhóm",),
              "security": ("bảo mật", "security"), "skill": ("kỹ năng", "skill"), "ctf": ("tạo đề",)}
PHASE_KIND = {"lit": "lit", "review": "review", "code": "code", "deploy": "code", "ctf": "code"}


def pick_assignee(phase, dept="", only_dept=False):
    """Chọn người hợp lý nhất: hợp phòng, hợp vai trò, rảnh, đã kết nối, ít việc. Trả về (id, lý do).
    only_dept=True: chỉ chọn trong phòng `dept` (lệnh gõ ở ô lệnh của phòng)."""
    s = load()
    open_tasks = {}
    for t in s["tasks"]:
        if t["column"] in ("todo", "doing") and t["owner"]:
            open_tasks[t["owner"]] = open_tasks.get(t["owner"], 0) + 1
    want = PHASE_DEPT.get(phase, "")
    want_dept = dept or next((d for d in ((want,) if isinstance(want, str) else want) if d in s["depts"]), "")
    best, best_score, best_why = None, -99, []
    for k, a in s["agents"].items():
        if a.get("system") or (only_dept and a["dept"] != dept):
            continue
        score, why = 0, []
        if a["dept"] == want_dept:
            score += 5
            why.append(f"đúng {s['depts'].get(want_dept, {}).get('name', want_dept)}")
        if any(w in a["title"].lower() for w in PHASE_ROLE.get(phase, ())):
            score += 3
            why.append(f"vai {a['title']}")
        kind = providers.PRESETS.get(a["provider"]["type"], {}).get("kind")
        if a.get("auto") and kind in ("cli", "api"):
            if a.get("conn", {}).get("ok") is False:
                score -= 2
                why.append("chưa kết nối")
            else:
                score += 3
                why.append("tự làm được")
        if (a.get("sleep_until") or 0) > now():
            score -= 6
            why.append("đang ngủ")
        elif a["status"] == "error":
            score -= 3
        elif a["status"] == "off":
            score -= 4
        elif a["status"] in ("idle", "waiting"):
            score += 1
            why.append("đang rảnh")
        n = open_tasks.get(k, 0)
        score -= n
        if n:
            why.append(f"đang ôm {n} việc")
        if score > best_score:
            best, best_score, best_why = k, score, why
    if best is None:
        raise ValueError("Chưa có nhân viên nào để giao")
    return best, ", ".join(best_why) or "còn trống"


PHASE_GUESS = [  # đoán loại việc từ lệnh gõ tự do (thứ tự = ưu tiên)
    ("ctf", r"tạo đề|ra đề|làm đề|đề ctf|đề chống ai|challenge"),
    ("skill", r"kỹ năng|skill"),
    ("security", r"bảo mật|security|lỗ hổng|vuln|pentest|tấn công|firewall|ssh|cve"),
    ("deploy", r"deploy|triển khai|lên vps|cập nhật lên|release"),
    ("review", r"\breview\b|phản biện|soát (bài|bản thảo|paper|lỗi chính tả)|kiểm tra bài|đọc lại bản thảo"),  # ranh giới từ: "previews/" không phải review; "soát" đứng một mình (bộ soát chữ, soát docs) cũng không
    ("lit", r"tài liệu|related work|survey|tìm \d* ?bài|bài báo|\bq1\b|a\*|trích dẫn|paper liên quan|gap"),
    ("experiment", r"thí nghiệm|experiment|baseline|chạy lại|seed|benchmark|train"),
    ("writing", r"viết|section|abstract|latex|bản thảo"),
    ("code", r"code|sửa|fix|bug|lỗi|tính năng|giao diện|trang|api"),
    ("results", r"kết quả|bảng|hình|figure|phân tích"),
]


def guess_phase(text):
    low = text.lower()
    return next((ph for ph, pat in PHASE_GUESS if re.search(pat, low)), "idea")


DELIVER = ("show", "file")  # 📺 hiển thị kết quả trong app · 📄 nhận file


SKILL_NOTE = ("\n\n[Cách làm của Phòng Kỹ năng] Tự TÌM TRÊN WEB (WebSearch/WebFetch) skill có sẵn đúng yêu cầu: ưu tiên "
              "github.com/anthropics/skills, các repo skill/awesome-claude-skills nhiều sao, tài liệu chính thức. Đọc kỹ, chọn nguồn uy tín "
              "và còn cập nhật, rồi TẢI VỀ: ghi thành skills/<ten-khong-dau>/SKILL.md (giữ nội dung gốc, dịch/rút gọn phần mô tả nếu cần), "
              "dòng đầu phần thân ghi 'Nguồn: <URL> · License: <...>'. File phụ (reference, script) chép nguyên văn vào cùng thư mục "
              "nhưng KHÔNG chạy. Không tìm được cái phù hợp thì tự viết, ghi rõ 'tự viết'. Báo cáo: đã tải skill nào, từ đâu, vì sao chọn.")


def _deliver_note(deliver, files_dir, dept=""):
    if dept == "skills":  # chỉ Phòng Kỹ năng mới đi tìm skill trên web
        return SKILL_NOTE
    if (load()["depts"].get(dept) or {}).get("auto_write"):  # phòng tự ghi trong thư mục làm việc riêng: không cần dặn nơi nộp
        return ""
    if deliver == "file":
        return (f"\n\n[Cách nhận kết quả] Sếp cần NHẬN FILE: ghi sản phẩm thành file trong thư mục {files_dir} "
                f"(trừ khi sếp chỉ rõ nơi khác). Cuối báo cáo liệt kê đường dẫn các file đã tạo.")
    return ("\n\n[Cách nhận kết quả] Sếp chỉ cần XEM kết quả trong app: trả lời thẳng trong báo cáo, gọn, dễ đọc. "
            "KHÔNG tạo hay sửa file nào.")


def room_command(dept, text, mode="read", flow="full", deliver="show"):
    """Ô lệnh của phòng: '@Tên việc…' giao thẳng cho người đó, không thì tự đoán loại việc và chọn người trong phòng."""
    text = text.strip()
    if not text:
        raise ValueError("Gõ lệnh trước đã")
    deliver = deliver if deliver in DELIVER else "show"
    if guess_phase(text) == "ctf":  # tạo đề luôn phải ghi file (gói đề trong thư mục đề tạm)
        deliver = "file"
    mode = "write" if deliver == "file" else "read"  # nhận file thì cần quyền ghi (xin duyệt), xem thì chỉ đọc
    if (load()["depts"].get(dept) or {}).get("auto_write"):  # vd. Phòng Kỹ năng: luôn tự ghi vào thư mục của phòng
        mode = "write"
    files_dir = ROOT / "outputs" / "files" / f"{datetime.now():%Y-%m-%d_%H%M%S}_{ascii_id(text) or 'viec'}"
    t = _room_command(dept, text, mode, flow, deliver, files_dir)
    set_task_fields(t["id"], deliver=deliver, files_dir=str(files_dir) if deliver == "file" else "")
    return {**t, "deliver": deliver}


def _room_command(dept, text, mode, flow, deliver, files_dir):
    s = load()
    if dept not in s["depts"]:
        raise ValueError("Không có phòng này")
    owner = "auto"
    m = re.match(r"@(\S+)\s+(.*)", text, re.S)
    if m:
        who = m.group(1).lower()
        hit = next((k for k, a in s["agents"].items() if not a.get("system") and who in (k, a["name"].lower())), None)
        if not hit:
            raise ValueError(f"Không có nhân viên tên {m.group(1)}")
        owner, text = hit, m.group(2).strip()
    phase = guess_phase(text)
    # Phòng không làm nghiên cứu (vd. phòng game): chữ "tài liệu", "soát", "Q1"… trong thư giao việc không được biến việc
    # thành tìm tài liệu / phản biện / viết bài (agent nhận lời dặn sai, bỏ việc thật). Loại nghiên cứu chỉ cho phòng research.
    if phase in ("lit", "review", "writing", "idea", "design", "experiment", "results") and dept != "research":
        phase = "code"
    title_src = text
    text = text + _deliver_note(deliver, files_dir, dept)
    title = title_src.splitlines()[0][:140]
    import workflow
    if workflow.enabled(dept):  # tôn ti: trưởng phòng giao việc (hoặc giao thẳng nếu sếp chỉ định @người)
        flow = flow if flow in workflow.FLOWS else "auto"
        why = ""
        if s["depts"][dept].get("flow") in workflow.FLOWS:  # phòng chốt sẵn quy trình (vd. Phòng Game: làm → sếp duyệt)
            flow, why = s["depts"][dept]["flow"], "quy trình của phòng"
        if flow == "auto":  # việc cơ bản 1 người làm; việc sâu mới chia nhiều người + duyệt 2 cấp
            flow = workflow.classify(title_src, phase)
            why = workflow.LEVEL_TEXT[flow]
        if owner == "auto" and flow != "full":  # không cần trưởng phòng chia việc: giao thẳng người hợp nhất
            owner, _ = pick_assignee(phase, dept, only_dept=True)
        r = (workflow.start_direct(dept, owner, text, mode, title, flow=flow) if owner and owner != "auto"
             else workflow.start(dept, text, mode, title, flow=flow))
        return {**r, "why": why or r.get("why", "")}
    return dispatch_task(title, phase, owner, dept, text, mode, True, (), only_dept=True)


def dispatch_task(title, phase="idea", owner="auto", dept="", body="", mode="read", run=True, inputs=(), only_dept=False):
    """Giao việc từ app: tự chọn người nếu cần, rồi gửi thư để nhân viên làm luôn."""
    why = ""
    if owner == "auto":
        owner, why = pick_assignee(phase, dept, only_dept)
    if run and owner and owner in load()["agents"]:
        import workflow
        odept = load()["agents"][owner]["dept"]
        if workflow.enabled(odept):  # phòng làm theo cấp bậc: qua trưởng phòng và các bước duyệt
            text = body or title
            return (workflow.start(odept, text, mode, title) if why else
                    workflow.start_direct(odept, owner, text, mode, title))
    t = add_task(title, owner, phase, actor="boss")
    if why:
        log(DEPUTY, f"Giao việc #{t['id']} cho {load()['agents'][owner]['name']} ({why})", kind="task")
    mail = None
    if run and owner:
        mail = send_mail("boss", owner, PHASE_KIND.get(phase, "task"), title, body, inputs, "", mode, "", task_id=t["id"])
    return {**t, "why": why, "mail": mail}


def move_task(task_id, column, actor=None):
    if column not in COLUMNS:
        raise ValueError(f"Cột phải là một trong: {', '.join(COLUMNS)}")
    with _lock:
        s = load()
        t = next((t for t in s["tasks"] if t["id"] == int(task_id)), None)
        if t is None:
            raise ValueError(f"Không có việc #{task_id}")
        if t["column"] == column:
            return t
        t.update(column=column, updated=now())
        save(s)
    log(actor or t.get("owner") or "boss", f"Việc #{t['id']} → {column}: {t['title']}",
        kind="done" if column == "done" else "task")
    if column == "done":
        for p in INBOX.glob("*.md"):  # thư còn chờ của việc đã đóng: huỷ
            if not p.name.endswith((".done.md", ".denied.md")) and str(parse_mail(p)[0].get("task", "")) == str(t["id"]):
                try:
                    p.rename(p.with_name(p.name[:-3] + ".denied.md"))
                except OSError:
                    pass
        workers_mod = sys.modules.get("workers")
        if workers_mod:
            workers_mod.cancel_task(t["id"])
    return t


def update_task(task_id, actor="boss", **fields):
    with _lock:
        s = load()
        t = next((t for t in s["tasks"] if t["id"] == int(task_id)), None)
        if t is None:
            raise ValueError(f"Không có việc #{task_id}")
        if fields.get("delete"):
            s["tasks"].remove(t)
            save(s)
            log(actor, f"Xoá việc #{t['id']}: {t['title']}", kind="task")
            return t
        for k in ("title", "owner", "phase"):
            if fields.get(k) is not None:
                t[k] = fields[k]
        t["updated"] = now()
        save(s)
    log(actor, f"Sửa việc #{t['id']}: {t['title']} (giao cho {t['owner'] or 'chưa ai'})", kind="task")
    return t


def set_task_fields(task_id, **fields):
    with _lock:
        s = load()
        t = next((x for x in s["tasks"] if x["id"] == int(task_id)), None)
        if t is None:
            return None
        t.update(fields, updated=now())
        save(s)
        return t


def note_run(task_id, reason, who, stage=""):
    """Ghi một lượt chạy AI của việc kèm lý do (hiện ở 👁 Đang làm gì, 📚 Kết quả, bảng công việc). Trả về số lượt."""
    with _lock:
        s = load()
        t = next((x for x in s["tasks"] if str(x["id"]) == str(task_id)), None)
        if t is None:
            return 0
        n = int(t.get("run_n", 0)) + 1
        t["run_n"] = n
        t["run_log"] = (t.get("run_log") or [])[-29:] + [{"n": n, "reason": reason or "lần đầu", "who": who,
                                                            "stage": stage, "t": now()}]
        save(s)
        return n


def get_task(task_id):
    return next((x for x in load()["tasks"] if str(x["id"]) == str(task_id)), None)


def _read_output(rel):
    p = (ROOT / rel).resolve() if rel else None
    if not p or not p.exists() or (ROOT / "outputs").resolve() not in p.parents:
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def task_result(task_id):
    """Kết quả để sếp xem: của chính việc + các việc con (trưởng phòng chia ra)."""
    t = get_task(task_id)
    if not t:
        raise ValueError(f"Không có việc #{task_id}")
    parts = []
    for x in [t] + [get_task(c) for c in t.get("children", [])]:
        if x and x.get("output"):
            who = load()["agents"].get(x["owner"], {}).get("name", x["owner"])
            head = f"# #{x['id']} · {who}: {x['title']}\n\n" if x is not t or t.get("children") else ""
            parts.append(head + _read_output(x["output"]))
    files_dir = t.get("files_dir", "")
    return {"id": t["id"], "title": t["title"], "column": t["column"], "deliver": t.get("deliver", ""),
            "text": "\n\n---\n\n".join(parts) or "Chưa có kết quả.",
            "files_dir": files_dir, "has_files": bool(files_dir and Path(files_dir).exists()
                                                      and any(Path(files_dir).iterdir()))}


GRANT_CMDS = ["Bash(python:*)", "Bash(py:*)", "Bash(pdflatex:*)", "Bash(latexmk:*)", "Bash(bibtex:*)",
              "Bash(biber:*)", "Bash(tectonic:*)", "Bash(cd:*)"]


PERMS = {"perm_write": "tự ghi file (không phải xin)", "perm_cmds": "chạy python / pdflatex / latexmk / bibtex",
         "perm_web": "tra web (WebSearch / WebFetch)"}


def set_perm(agent_id, perm, on):
    """Quyền thường trực của một nhân viên, sếp bật/tắt ở Phòng Cấp quyền."""
    if perm not in PERMS:
        raise ValueError("Không có quyền này")
    with _lock:
        s = load()
        a = s["agents"].get(agent_id)
        if not a or a.get("system"):
            raise ValueError("Không có nhân viên này")
        a[perm] = bool(on)
        save(s)
    log("boss", f"{'🔓 Cấp' if on else '🔒 Thu'} quyền {PERMS[perm]} cho {a['name']}", kind="hr", to=agent_id)
    return {"ok": True}


def grant_task(task_id, approval_id="", cmds=False):
    """Sếp bấm 🔓 Cấp quyền: việc chuyển sang chế độ ghi (kèm chạy python/pdflatex nếu chọn) rồi chạy lại ngay.
    Quyền này coi như sếp đã duyệt: nhân viên không phải xin lại."""
    t = get_task(task_id)
    if not t:
        raise ValueError(f"Không có việc #{task_id}")
    if t.get("external"):  # phản biện mù / thử đề: giao lại theo cách thường sẽ mất tính "mù"
        raise ValueError("Việc này chạy bằng công cụ riêng (phản biện mù), không giao lại được. Chạy lại công cụ đó.")
    req = re.sub(r"\n*\[Cách nhận kết quả\][^\n]*", "", t.get("request") or t["title"]).rstrip()
    grant = ("\n\n[Quyền] Sếp đã CẤP QUYỀN GHI FILE" + (" và CHẠY LỆNH python / pdflatex / latexmk / bibtex" if cmds else "")
             + " cho việc này. Làm luôn, không hỏi lại về quyền. Cuối báo cáo liệt kê các file đã sửa/tạo.")
    set_task_fields(t["id"], request=req + grant, mode="write", granted_write=True, allow_cmds=bool(cmds),
                    deliver="file" if t.get("deliver") == "show" else t.get("deliver", ""))
    # dừng lượt cũ (chế độ đọc) và huỷ thư cũ của việc này, tránh chạy 2 lần
    for p in INBOX.glob("*.md"):
        if not p.name.endswith((".done.md", ".denied.md")) and str(parse_mail(p)[0].get("task", "")) == str(t["id"]):
            try:
                p.rename(p.with_name(p.name[:-3] + ".denied.md"))
            except OSError:
                pass
    w = sys.modules.get("workers")
    if w:
        w.cancel_task(t["id"])
    log("boss", f"🔓 Cấp quyền ghi{' + chạy lệnh' if cmds else ''} cho việc #{t['id']}: {t['title'][:70]}", kind="task",
        to=t.get("owner") or None)
    note = "Sếp đã cấp quyền ghi file" + (" và chạy lệnh python/pdflatex" if cmds else "") + ". Làm luôn theo phương án đã đề xuất."
    pend = next((a for a in load()["approvals"] if a["status"] == "pending"
                 and (a["id"] == approval_id or (not approval_id and str(a.get("ref")) == str(t["id"]) and a["kind"] == "ask"))), None)
    if pend:  # đang chờ sếp trả lời [CẦN SẾP]: trả lời luôn, việc chạy tiếp ở chế độ ghi
        decide(pend["id"], True, note)
        return {"ok": True, "id": t["id"], "resent": True}
    t = get_task(t["id"])
    body = f"📌 {note}\n\n## Yêu cầu\n{t['request']}"
    if t.get("output"):
        body += f"\n\n## Kết quả lần trước\n{_read_output(t['output'])[:6000]}"
    if t.get("stage"):
        import workflow
        set_task_fields(t["id"], stage="work")
        workflow._send_work(t["id"], body, frm="boss", reason="sếp bấm 🔓 cấp quyền ghi" + (" + chạy lệnh" if cmds else ""))
    else:
        send_mail("boss", t["owner"], "task", t["title"], body, mode="write", task_id=t["id"],
                  reason="sếp bấm 🔓 cấp quyền ghi" + (" + chạy lệnh" if cmds else ""))
        move_task(t["id"], "todo", actor="boss")
    return {"ok": True, "id": t["id"], "resent": True}


# ---------- terminal của sếp (chạy lệnh nhân viên nhờ, ngay trong app) ----------
_TERM = {}


def _bash_exe():
    import shutil
    for p in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
        if p and Path(p).exists() and "system32" not in p.lower():  # bỏ bash của WSL
            return p
    return None


def term_start(cmd, cwd="", shell="bash"):
    """Sếp bấm ▶ Chạy: chạy lệnh trên máy này (chỉ sếp mở được app), đọc dần kết quả bằng term_poll."""
    import subprocess
    cmd = str(cmd).strip()
    if not cmd:
        raise ValueError("Gõ lệnh trước đã")
    cwd = str(cwd or "").strip() or str(ROOT)
    if not Path(cwd).is_dir():
        raise ValueError(f"Không có thư mục {cwd}")
    if shell == "bash":
        exe = _bash_exe()
        if not exe:
            raise ValueError("Máy chưa có Git Bash, chọn PowerShell")
        argv = [exe, "-lc", cmd]
    else:
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    jid = f"t{now()}{len(_TERM)}"
    job = {"out": [], "done": False, "code": None, "cmd": cmd, "cwd": cwd, "proc": proc, "t": now()}
    _TERM[jid] = job

    def pump():
        timer = threading.Timer(1800, proc.kill)
        timer.start()
        for raw in iter(proc.stdout.readline, b""):
            job["out"].append(raw.decode("utf-8", errors="replace"))
            if len(job["out"]) > 4000:
                del job["out"][:1000]
        job["code"] = proc.wait()
        job["done"] = True
        timer.cancel()
        log("boss", f"🖥️ Lệnh xong (mã {job['code']}): {cmd[:90]}", kind="log")

    threading.Thread(target=pump, daemon=True).start()
    log("boss", f"🖥️ Sếp chạy lệnh trong {cwd}: {cmd[:120]}", kind="log")
    for k in [k for k, j in _TERM.items() if j["done"] and now() - j["t"] > 3600]:
        _TERM.pop(k, None)
    return {"id": jid}


def term_poll(jid, stop=False):
    j = _TERM.get(jid)
    if not j:
        raise ValueError("Phiên terminal đã hết")
    if stop and not j["done"]:
        j["proc"].kill()
    return {"out": "".join(j["out"])[-60000:], "done": j["done"], "code": j["code"]}


# ---------- 🧪 Phòng Thử đề: thử một đề bất kỳ, đề ĐẠT thì giao người deploy ----------
_TEST = {"proc": None, "what": "", "cache": None, "t": 0}


def tester_available():
    """Bản chia sẻ không kèm Phòng Thử đề CTF (tools/tester.py): mọi chức năng thử đề tự tắt."""
    return (ROOT / "tools" / "tester.py").exists()


def _need_tester():
    if not tester_available():
        raise ValueError("Bản này không có Phòng Thử đề (thiếu tools/tester.py)")


def _test_running():
    p = _TEST["proc"]
    return _TEST["what"] if p and p.poll() is None else ""


def tester_list():
    if not tester_available():
        return {"items": [], "running": ""}
    if not _TEST["cache"] or now() - _TEST["t"] > 15 or (_TEST["what"] and not _test_running()):
        import importlib
        import tester
        importlib.reload(tester)  # sửa tools/tester.py không cần khởi động lại văn phòng
        _TEST.update(cache=tester.listing(), t=now())
        if not _test_running():
            _TEST["what"] = ""
    return {"items": _TEST["cache"], "running": _test_running()}


def _test_item(where, slug):
    _need_tester()
    import tester
    w = Path(where).resolve()
    if tester.CHALL_ROOT.resolve() not in [w, *w.parents]:
        raise ValueError("Đề phải nằm trong E:\\CTF\\challenges")
    it = next((x for x in tester.items(w) if x["slug"] == slug), None)
    if not it:
        raise ValueError(f"Không thấy đề {slug}")
    return w, it


def tester_run(where, slug):
    """Sếp bấm 🧪 Thử: Mò giải mù đề này 2 phút (chạy nền, một đề một lúc)."""
    import subprocess
    if _test_running():
        raise ValueError(f"Mò đang thử {_test_running()}, chờ xong đã")
    w, it = _test_item(where, slug)
    py = Path(sys.executable)
    py = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists() else py
    logf = open(ROOT / "state" / "tester-last.log", "w", encoding="utf-8")
    _TEST["proc"] = subprocess.Popen([str(py), str(ROOT / "tools" / "tester.py"), str(w), slug, "--force", "--boss"], cwd=str(ROOT),
                                     stdout=logf, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _TEST.update(what=it["name"], t=0)
    log("boss", f"🧪 Giao Mò thử giải mù: {it['name']}", kind="mail", to="mo")
    return {"ok": True, "running": it["name"]}


def tester_run_wait(where, timeout=1800):
    """Mò thử mù cả gói đề rồi trả về chữ kết quả (chờ tới lượt nếu Mò đang thử đề khác). Không tốn lượt AI của văn phòng."""
    import subprocess
    if not tester_available():
        return 1, "⚠️ LỖI: bản này không có Phòng Thử đề (thiếu tools/tester.py)"
    end = time.time() + 3600
    while _test_running() and time.time() < end:
        time.sleep(5)
    py = Path(sys.executable)
    py = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists() else py
    proc = subprocess.Popen([str(py), str(ROOT / "tools" / "tester.py"), str(where), "--force"], cwd=str(ROOT),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _TEST.update(proc=proc, what=Path(where).name, t=0)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        out = "⚠️ LỖI: Mò thử quá giờ"
    return proc.returncode, out or ""


def tester_deploy(where, slug, publish=False):
    """Sếp bấm 🚀 Giao deploy: đề đã ĐẠT bài thử → người deploy của Phòng CLB đăng lên portal."""
    _need_tester()
    import tester
    import workflow
    w, it = _test_item(where, slug)
    row = next((x for x in tester.listing() if x["where"] == it["where"] and x["slug"] == slug), {})
    if row.get("result") != "dat" or row.get("stale"):
        raise ValueError("Đề chưa ĐẠT bài thử AI (hoặc đã sửa sau lần thử): bấm 🧪 Thử trước")
    if not row.get("deployable"):
        raise ValueError("Đề kiểu cũ (đã có trên portal): không đăng lại bằng công cụ này")
    s = load()
    staff = [k for k, a in s["agents"].items() if "clb" in (a["dept"], a.get("work_dept")) and not a.get("system")]
    who = next((k for k in staff if "deploy" in s["agents"][k].get("title", "").lower()), s["depts"]["clb"].get("head"))
    rel = w.relative_to(tester.CHALL_ROOT.parent).as_posix()  # vd challenges/nhap/anti-ai-web
    cmd = f"bash scripts/add_challenges.sh {rel} --only {slug}{' --publish' if publish else ''}"
    text = (f"Đăng đề **{it['name']}** (`{slug}`, gói {w}) lên portal "
            f"{'CÔNG KHAI (sếp đã đồng ý)' if publish else 'dạng NHÁP'}.\n"
            f"Chạy trong E:\\CTF (Bash timeout 600000): `{cmd}`\n"
            "Đề đã ĐẠT bài thử AI; script tự kiểm tra lại, có lỗi thì sửa theo thông báo của script (không sửa nội dung đề, "
            "không tự giải đề, "
            "không sửa _thu-de.json), không được thì ghi [CẦN SẾP].\n"
            "Báo cáo: id đề trên portal, trạng thái (nháp/công khai), port và trạng thái máy đề (nếu có). Không ghi flag.")
    title = f"🚀 Đăng đề {it['name']}{' (công khai)' if publish else ' (nháp)'}"
    t = workflow.start_direct("clb", who, text, "write", title, flow="fast")
    set_task_fields(t["id"], granted_write=True, deliver="show")  # sếp bấm nút = đã duyệt
    log("boss", f"🚀 Giao {s['agents'][who]['name']} đăng đề {it['name']}", kind="mail", to=who)
    return {"id": t["id"], "owner": who}


def _kill_tree(proc):
    """Dừng tiến trình và mọi tiến trình con (claude.exe, python của nhân viên…)."""
    import subprocess
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except OSError:
            pass


def _procs():
    """Danh sách tiến trình (pid, cha, dòng lệnh) qua PowerShell; lỗi thì trả rỗng."""
    import subprocess
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return json.loads(r.stdout or "[]")
    except Exception:  # noqa: BLE001
        return []


def _kill_testers(only_orphans=False):
    """Dừng công cụ thử đề + Claude của Mò (chạy trong E:\\CTF-ThuDe). only_orphans: chỉ những cái mất tiến trình cha."""
    import subprocess
    ps = _procs()
    alive = {p["ProcessId"] for p in ps}
    hit = [p for p in ps if any(k in (p.get("CommandLine") or "") for k in ("tester.py", "CTF-ThuDe", "ctftest-"))
           and (not only_orphans or p["ParentProcessId"] not in alive)]
    for p in hit:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p["ProcessId"])], capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if hit:
        set_status("mo", "idle", "")
        set_model_now("mo", "")
    return len(hit)


def stop_dept(dept):
    """■ Dừng cả phòng: dừng mọi người trong phòng đang chạy / đang chờ / còn việc mở."""
    s = load()
    if dept not in s["depts"]:
        raise ValueError("Không có phòng này")
    stopped = []
    for k, a in s["agents"].items():
        if a["dept"] != dept:
            continue
        busy = a.get("status") in ("working", "waiting") or any(
            t["owner"] == k and t["column"] in ("todo", "doing") for t in s["tasks"])
        if busy or (k == "mo" and _test_running()):
            r = stop_agent(k)
            if r.get("stopped") or busy:
                stopped.append(a["name"])
    _kill_testers(only_orphans=dept != "thu-de")
    if dept == "thu-de":
        _kill_testers()
    log("boss", f"■ Sếp dừng cả {s['depts'][dept]['name']}: {', '.join(stopped) or 'không ai đang chạy'}", kind="task")
    return {"ok": True, "stopped": stopped}


def stop_agent(agent_id):
    """Sếp bấm ■ Dừng: dừng ngay lượt đang chạy của nhân viên và đóng việc đó (huỷ thư còn chờ của việc)."""
    s = load()
    a = s["agents"].get(agent_id)
    if not a:
        raise ValueError("Không có nhân viên này")
    if agent_id == "mo":  # Mò: dừng mọi lượt thử đang chạy (sếp bấm hoặc người tạo đề tự gọi)
        what = _test_running() or a.get("task", "")
        if _TEST["proc"] and _test_running():
            _kill_tree(_TEST["proc"])
        n = _kill_testers()
        set_status(agent_id, "idle", "")
        log("boss", f"■ Dừng Mò{': ' + what if what else ''}", kind="task", to=agent_id)
        return {"ok": True, "stopped": what if (what or n) else ""}
    w = sys.modules.get("workers")
    run = (w._running.get(agent_id) if w else None)
    tid = run[0] if run else None
    if tid is None:  # không có lượt đang chạy: lấy việc đang mở mới nhất của người này
        open_t = sorted([t for t in s["tasks"] if t["owner"] == agent_id and t["column"] in ("todo", "doing")],
                        key=lambda t: t["updated"], reverse=True)
        tid = open_t[0]["id"] if open_t else None
    if run:
        _kill_tree(run[1])
    if tid is None:
        set_status(agent_id, "idle", "")
        return {"ok": True, "stopped": ""}
    t = get_task(tid)
    set_task_fields(tid, stage="cancelled")
    move_task(tid, "done", actor="boss")  # huỷ thư còn chờ của việc + dừng lượt chạy (nếu còn)
    set_status(agent_id, "idle", "")
    clear_steps(agent_id) if "clear_steps" in globals() else None
    if run:
        time.sleep(1)
        _kill_testers(only_orphans=True)  # Mò do người này gọi bị bỏ lại khi cây tiến trình đứt
    log("boss", f"■ Sếp dừng việc #{tid} của {a['name']}: {t['title'][:80]}", kind="task", to=agent_id)
    return {"ok": True, "stopped": t["title"], "id": tid}


def archive_tasks(ids=None, done=False):
    """🧹 Dọn việc: cất việc đã xong / đã dừng khỏi bảng và 📚 Kết quả. File kết quả vẫn giữ trong outputs/.
    ids: cất đúng các việc này (đang làm thì dừng trước); done: cất mọi việc đã xong / đã dừng."""
    with _lock:
        s = load()
        want = {int(i) for i in ids or []}
        hit = [t for t in s["tasks"] if (t["id"] in want) or (done and t["column"] == "done")]
        busy = [t["id"] for t in hit if t["id"] in want and t["column"] != "done"]
    for tid in busy:  # cất việc đang mở: dừng và đóng trước
        set_task_fields(tid, stage="cancelled")
        move_task(tid, "done", actor="boss")
    with _lock:
        s = load()
        n = 0
        for t in s["tasks"]:
            if (t["id"] in want) or (done and t["column"] == "done"):
                if not t.get("archived"):
                    t["archived"] = now()
                    n += 1
        save(s)
    log("boss", f"🧹 Dọn {n} việc khỏi bảng", kind="task")
    return {"ok": True, "n": n}


def open_files(task_id):
    t = get_task(task_id) or {}
    d = Path(t.get("files_dir") or "")
    if not t.get("files_dir") or not d.exists():
        raise ValueError("Việc này chưa có file")
    os.startfile(str(d))  # noqa: S606 — chỉ mở thư mục của văn phòng trên máy sếp
    return {"ok": True}


def _light_ai(system, facts, timeout=240):
    """Gọi model nhẹ nhất đang dùng được (1 lượt)."""
    s = load()
    choices = [("antigravity-cli", "gemini-3.8-flash-low"), ("claude-cli", "haiku"), ("gemini-api", "gemini-2.5-flash")]
    have = {a["provider"]["type"]: k for k, a in s["agents"].items() if a.get("conn", {}).get("ok")}
    for typ, model in choices:
        if typ in have:
            reply = providers.run({"type": typ, "model": model}, get_secret(have[typ]), system, facts, timeout=timeout)
            record_use(have[typ], usage=getattr(reply, "usage", None))
            return str(reply).strip(), model
    raise ValueError("Chưa có nhân viên nào kết nối được để tóm tắt bằng AI")


def dept_summary(dept, limit=10):
    """Nút '🧾 Tổng hợp kết quả' của phòng: AI gộp kết quả các việc phòng đã làm xong gần đây thành một bản."""
    s = load()
    if dept not in s["depts"]:
        raise ValueError("Không có phòng này")
    staff = {k for k, a in s["agents"].items() if a["dept"] == dept}
    done = [t for t in s["tasks"] if (t.get("dept") == dept or t["owner"] in staff)
            and t["column"] in ("review", "done") and t.get("output")]  # gồm cả việc con: kết quả nằm ở đó
    pool = sorted(done, key=lambda x: x["updated"], reverse=True)[:limit]
    if not pool:
        raise ValueError("Phòng chưa có việc nào xong để tổng hợp")
    facts = []
    for t in pool:
        body = _read_output(t["output"])
        m = re.search(r"^#+\s*Tóm tắt.*?$(.*?)(?=^#+\s|\Z)", body, re.M | re.S | re.I)
        keep = (m.group(1).strip() + "\n\n" + body[:2500]) if m else body[:3500]
        who = s["agents"].get(t["owner"], {}).get("name", t["owner"])
        facts.append(f"### Việc #{t['id']} ({who}, {'đã ký' if t['column'] == 'done' else 'chờ sếp'}): {t['title']}\n{keep[:4000]}")
    text, model = _light_ai(
        "Bạn là thư ký tổng hợp cho sếp. Dựa CHỈ vào kết quả các việc dưới đây, viết bản TỔNG HỢP tiếng Việt: "
        "## Tóm tắt (3-5 dòng), ## Kết quả chính (gạch đầu dòng theo việc, có số liệu/kết luận cụ thể), "
        "## Việc còn dở / rủi ro, ## Sếp cần quyết. Không bịa thêm, không lặp lại nguyên văn.",
        "\n\n".join(facts))
    d = ROOT / "outputs" / "_tonghop"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{dept}_{datetime.now():%Y-%m-%d_%H%M%S}.md"
    f.write_text(f"# Tổng hợp {s['depts'][dept]['name']} ({len(pool)} việc)\n\n{text}\n", encoding="utf-8")
    log(DEPUTY, f"Tổng hợp kết quả {s['depts'][dept]['name']} ({len(pool)} việc)", kind="done")
    return {"text": text, "model": model, "count": len(pool), "file": str(f.relative_to(ROOT)),
            "tasks": [t["id"] for t in pool]}


# ---------- Sổ nội quy của sếp ----------

def charter_add(text):
    text = str(text).strip()
    if not text:
        raise ValueError("Ghi nội dung yêu cầu trước đã")
    with _lock:
        s = load()
        s.setdefault("charter", [])
        cid = max([c["id"] for c in s["charter"]] + [0]) + 1
        s["charter"].append({"id": cid, "text": text[:1500], "on": True, "t": now()})
        save(s)
    log("boss", f"Thêm nội quy #{cid}: {text[:80]}", kind="policy")
    return {"id": cid}


def charter_update(cid, d):
    with _lock:
        s = load()
        c = next((x for x in s.get("charter", []) if x["id"] == int(cid)), None)
        if c is None:
            raise ValueError("Không có nội quy này")
        if d.get("delete"):
            s["charter"].remove(c)
        else:
            if d.get("text") is not None:
                c["text"] = str(d["text"]).strip()[:1500]
            if d.get("on") is not None:
                c["on"] = bool(d["on"])
        save(s)
    return {"ok": True}


def charter_text():
    items = [c["text"] for c in load().get("charter", []) if c.get("on", True)]
    return "\n".join(f"{i}. {x}" for i, x in enumerate(items, 1))


def slug(text, n=40):
    return re.sub(r"[^\w\-]+", "-", text.lower(), flags=re.UNICODE).strip("-")[:n] or "thu"


def send_mail(frm, to, kind, subject, body="", inputs=(), output="", mode="read", workdir="", task_id=None,
              for_dept="", stage="", reason=""):
    if kind not in MAIL_KINDS:
        raise ValueError(f"Loại thư phải là một trong: {', '.join(MAIL_KINDS)}")
    if mode not in ("read", "write"):
        raise ValueError("Chế độ phải là read hoặc write")
    s = load()
    if to not in s["agents"]:
        raise ValueError(f"Không có nhân viên '{to}'")
    if not subject.strip():
        raise ValueError("Thiếu tiêu đề thư")
    workdir = workdir.strip() or s["depts"].get(s["agents"][to]["dept"], {}).get("workdir", "")
    if workdir and not Path(workdir).is_absolute():
        workdir = str(ROOT / workdir)
    if output and (Path(output).is_absolute() or ".." in Path(output).parts):
        raise ValueError("Nơi ghi kết quả phải là đường dẫn tương đối bên trong ResearchLab")
    INBOX.mkdir(exist_ok=True)
    name = f"{datetime.now():%Y-%m-%d_%H%M%S}_{frm}_to_{to}_{slug(subject)}.md"
    n = 2
    while any((INBOX / name.replace(".md", sfx)).exists() for sfx in (".md", ".done.md", ".denied.md")):
        name = f"{datetime.now():%Y-%m-%d_%H%M%S}-{n}_{frm}_to_{to}_{slug(subject)}.md"  # không ghi đè thư cùng giây
        n += 1
    head = ["---", f"from: {frm}", f"to: {to}", f"kind: {kind}", f"subject: {subject}"]
    if inputs:
        head.append("inputs:")
        head += [f"  - {p}" for p in inputs if p.strip()]
    if output:
        head.append(f"output: {output}")
    head.append(f"mode: {mode}")
    if task_id:
        head.append(f"task: {task_id}")
    if for_dept:
        head.append(f"for_dept: {for_dept}")
    if stage:  # bước trong quy trình cấp bậc (assign / work / lead_review / deputy_review)
        head.append(f"stage: {stage}")
    if workdir:
        head.append(f"workdir: {workdir}")
    if reason:  # vì sao có lượt chạy này (lần đầu / bị trả lại / sếp trả lời / cấp quyền / thử lại sau lỗi)
        head.append(f"reason: {' '.join(str(reason).split())[:240]}")
    head.append("---")
    (INBOX / name).write_text("\n".join(head) + "\n\n" + body.strip() + "\n", encoding="utf-8")
    log(frm, f"Gửi thư cho {s['agents'][to]['name']}: {subject}", kind="mail", to=to)  # app vẽ phong thư bay
    return name


def parse_mail(path):
    text = Path(path).read_text(encoding="utf-8")
    meta, body = {}, text
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?(.*)", text, re.S)
    if m:
        body, key = m.group(2), None
        for line in m.group(1).splitlines():
            if line.startswith("  - ") and key:
                meta.setdefault(key, []).append(line[4:].strip())
            elif ":" in line:
                key, val = (x.strip() for x in line.split(":", 1))
                meta[key] = val if val else []
    return meta, body.strip()


def inbox_items():
    if not INBOX.exists():
        return []
    items = []
    for p in sorted(INBOX.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
        meta, body = parse_mail(p)
        if not meta.get("to"):
            meta = {**_route_from_name(p.name), **meta}
            meta.setdefault("subject", _first_line(body) or p.stem)
        items.append({"file": p.name, "done": p.name.endswith((".done.md", ".denied.md")),
                      "denied": p.name.endswith(".denied.md"), "t": int(p.stat().st_mtime), "mode": meta.get("mode", "read"),
                      "from": meta.get("from", ""), "to": meta.get("to", ""), "kind": meta.get("kind", ""),
                      "subject": meta.get("subject", p.stem), "output": meta.get("output", ""),
                      "stage": meta.get("stage", ""), "for_dept": meta.get("for_dept", "")})
    return items


def _route_from_name(name):
    """Thư nhân viên tự đặt tên kiểu <ngày>_<người gửi>_to_<người nhận>_<chủ đề>.md."""
    m = re.search(r"_([a-z0-9-]+)_to_([a-z0-9-]+)_", name.lower())
    return {"from": m.group(1), "to": m.group(2)} if m else {}


def _first_line(body):
    return next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), "")


# ---------- Việc đang chờ sếp ----------

BOSS_NAMES = ("thuky", "boss", "sep", "pho-sep", "phosep")
_asks_cache = {"t": 0, "items": []}
_issues_cache = {"t": 0, "n": 0}


def issues_count():
    if now() - _issues_cache["t"] > 10:
        try:
            import troubleshoot
            _issues_cache.update(t=now(), n=len(troubleshoot.diagnose()))
        except Exception:  # noqa: BLE001
            _issues_cache["t"] = now()
    return _issues_cache["n"]


def _ask_files():
    """Thư nhân viên gửi sếp/Thư ký: trong hộp thư, và cả thư để nhầm trong thư mục làm việc của các phòng."""
    s = load()
    roots = {INBOX}
    for d in s["depts"].values():
        for x in [d.get("workdir", "")] + list(d.get("dirs", [])):
            if x:
                p = Path(x) if Path(x).is_absolute() else ROOT / x
                if p.is_dir():
                    roots.add(p)
    found = []
    for r in roots:
        pats = ["*.md"] if r == INBOX else ["*_to_thuky_*.md", "*/*_to_thuky_*.md", "*_to_boss_*.md", "*/*_to_boss_*.md"]
        for pat in pats:
            found += [p for p in r.glob(pat) if p.is_file()]
    handled = set(s.get("asks_done", []))
    out = []
    for p in found:
        if p.name.endswith((".done.md", ".denied.md")) or str(p) in handled:
            continue
        meta, body = parse_mail(p)
        route = {**_route_from_name(p.name), **{k: v for k, v in meta.items() if k in ("from", "to")}}
        if route.get("to") not in BOSS_NAMES:
            continue
        out.append({"path": str(p), "from": route.get("from", ""), "subject": meta.get("subject") or _first_line(body) or p.stem,
                    "body": body[:4000], "t": int(p.stat().st_mtime), "misplaced": p.parent != INBOX})
    return sorted(out, key=lambda x: x["t"], reverse=True)


def waiting():
    """Mọi thứ đang chờ sếp: yêu cầu duyệt/ký, câu hỏi của nhân viên, kết quả nhỏ chờ xem."""
    if now() - _asks_cache["t"] > 10:  # quét thư mục tốn công: 10 giây một lần là đủ
        _asks_cache.update(t=now(), items=_ask_files())
    s = load()
    return {"approvals": [a for a in s["approvals"] if a["status"] == "pending"],
            "asks": _asks_cache["items"],
            "results": [t for t in s["tasks"] if t["column"] == "review" and t["title"].startswith("📬")]}


def _mark_ask(path):
    with _lock:
        s = load()
        s.setdefault("asks_done", [])
        if path not in s["asks_done"]:
            s["asks_done"] = (s["asks_done"] + [path])[-500:]
        save(s)
    p = Path(path)
    if p.parent == INBOX and p.exists() and not p.name.endswith((".done.md", ".denied.md")):
        try:  # thư trong hộp thư đã xử lý: đóng lại, để không còn mũi tên "đang gửi" trên bản đồ
            p.rename(p.with_name(p.name[:-3] + ".done.md"))
        except OSError:
            pass
    _asks_cache["t"] = 0


def ask_reply(path, text):
    """Sếp trả lời câu hỏi của nhân viên: gửi thư ngược lại cho người hỏi để họ làm tiếp."""
    a = next((x for x in _ask_files() if x["path"] == path), None)
    if a is None:
        raise ValueError("Không còn thư này")
    if not str(text).strip():
        raise ValueError("Ghi câu trả lời trước đã")
    to = a["from"] if a["from"] in load()["agents"] else ""
    if to:
        send_mail("boss", to, "task", f"Sếp trả lời: {a['subject'][:90]}",
                  f"Sếp trả lời thư của bạn:\n\n{text.strip()}\n\n---\nThư gốc ({Path(path).name}):\n{a['body'][:2500]}")
    _mark_ask(path)
    log("boss", f"Trả lời {load()['agents'].get(to, {}).get('name', a['from'])}: {text.strip()[:80]}", kind="mail", to=to or None)
    return {"ok": True, "sent_to": to}


def ask_dismiss(path):
    _mark_ask(path)
    return {"ok": True}


# ---------- nhân sự & phòng ban ----------

def _clean_provider(p):
    t = p.get("type", "manual")
    if t not in providers.PRESETS:
        raise ValueError(f"Không biết loại nhà cung cấp '{t}'")
    out = {"type": t}
    for k in ("model", "base_url"):
        if p.get(k):
            out[k] = str(p[k]).strip()
    return out


def _apply_agent_fields(a, d, depts):
    for k in ("name", "title", "plant"):
        if d.get(k) is not None:
            a[k] = str(d[k]).strip()[:60]
    if d.get("role") is not None:  # vai trò / cách làm việc, đưa vào lời dặn khi nhân viên làm
        a["role"] = str(d["role"]).strip()[:2000]
    if d.get("color") and re.fullmatch(r"#[0-9a-fA-F]{6}", d["color"]):
        a["color"] = d["color"]
    if d.get("hat") in HATS:
        a["hat"] = d["hat"]
    if d.get("dept") is not None and not a.get("system"):
        if d["dept"] not in depts:
            raise ValueError("Phòng ban không tồn tại")
        a["dept"] = d["dept"]
    if d.get("provider") is not None and not a.get("system"):
        a["provider"] = _clean_provider(d["provider"])
    if d.get("auto") is not None and not a.get("system"):
        a["auto"] = bool(d["auto"])
    if isinstance(d.get("actions"), list):  # nút việc riêng: [{label, text, deliver, flow}]
        a["actions"] = [{"label": str(x.get("label", ""))[:40], "text": str(x.get("text", ""))[:1500],
                         "deliver": x.get("deliver") if x.get("deliver") in DELIVER else "show",
                         **({"flow": x["flow"]} if x.get("flow") in ("fast", "standard", "full") else {})}
                        for x in d["actions"][:6] if x.get("label") and x.get("text")]


def add_agent(d):
    name = str(d.get("name", "")).strip()
    if not name:
        raise ValueError("Thiếu tên nhân viên")
    with _lock:
        s = load()
        base = ascii_id(name) or "nv"
        aid, i = base, 2
        while aid in s["agents"] or aid == "boss":
            aid, i = f"{base}-{i}", i + 1
        a = json.loads(json.dumps(AGENT_BLANK))
        _apply_agent_fields(a, d, s["depts"])
        a["since"] = now()
        s["agents"][aid] = a
        save(s)
    log("boss", f"Tuyển {name} vào {s['depts'][a['dept']]['name']} ({providers.PRESETS[a['provider']['type']]['label']})", kind="hr")
    return {"id": aid}


def update_agent(aid, d):
    with _lock:
        s = load()
        if aid not in s["agents"]:
            raise ValueError(f"Không có nhân viên '{aid}'")
        _apply_agent_fields(s["agents"][aid], d, s["depts"])
        save(s)
    return {"id": aid}


def remove_agent(aid):
    with _lock:
        s = load()
        if s["agents"].get(aid, {}).get("system"):
            raise ValueError("Không cho nghỉ được: Thư ký và Phó sếp giữ hàng đợi duyệt")
        a = s["agents"].pop(aid, None)
        if a is None:
            raise ValueError(f"Không có nhân viên '{aid}'")
        for t in s["tasks"]:
            if t["owner"] == aid and t["column"] != "done":
                t["owner"] = ""
        save(s)
    set_secret(aid, "")
    log("boss", f"{a['name']} đã nghỉ việc. Việc dang dở chuyển về 'chưa giao'.", kind="hr")
    return {"ok": True}


def add_dept(name, icon="🏠", workdir="", notes=""):
    name = name.strip()
    if not name:
        raise ValueError("Thiếu tên phòng")
    with _lock:
        s = load()
        did = ascii_id(name) or "phong"
        while did in s["depts"]:
            did += "-2"
        s["depts"][did] = {"name": name, "icon": icon or "🏠", "workdir": workdir.strip(), "notes": notes.strip(),
                           "order": max([x["order"] for x in s["depts"].values()] + [0]) + 1}
        save(s)
    log("boss", f"Mở {icon} {name}", kind="hr")
    return {"id": did}


def update_dept(did, d):
    with _lock:
        s = load()
        dept = s["depts"].get(did)
        if dept is None:
            raise ValueError("Không có phòng này")
        for k in ("name", "icon", "workdir", "notes"):
            if d.get(k) is not None:
                dept[k] = str(d[k]).strip()
        if d.get("allow_commands") is not None:  # cho chạy lệnh (ssh, deploy…) khi việc đã được sếp duyệt
            dept["allow_commands"] = bool(d["allow_commands"])
        if d.get("dirs") is not None:  # thư mục phòng được phép vào (ngoài thư mục làm việc)
            ds = d["dirs"].splitlines() if isinstance(d["dirs"], str) else d["dirs"]
            dept["dirs"] = [x.strip() for x in ds if x.strip()]
        if d.get("head") is not None:
            dept["head"] = d["head"] if d["head"] in s["agents"] else ""
        if d.get("workflow") is not None:
            dept["workflow"] = bool(d["workflow"])
        if d.get("skills") is not None:
            dept["skills"] = [x for x in d["skills"] if (SKILLS / x / "SKILL.md").exists()]
        if d.get("allowed_tools") is not None:
            tools = d["allowed_tools"]
            dept["allowed_tools"] = [x.strip() for x in (tools.split(",") if isinstance(tools, str) else tools) if x.strip()]
        save(s)
    return {"id": did}


def remove_dept(did, move_to=None):
    with _lock:
        s = load()
        if s["depts"].get(did, {}).get("system"):
            raise ValueError("Không đóng được quầy lễ tân")
        staff = [a for a in s["agents"].values() if a["dept"] == did]
        if staff:
            if not move_to or move_to == did or move_to not in s["depts"] or s["depts"][move_to].get("system"):
                raise ValueError("Phòng còn nhân viên, chọn phòng để chuyển họ sang trước")
            for a in staff:
                a["dept"] = move_to
        d = s["depts"].pop(did, None)
        if d is None:
            raise ValueError("Không có phòng này")
        save(s)
    log("boss", f"Đóng {d['name']}", kind="hr")
    return {"ok": True}


def check_agent(aid):
    """Kiểm tra kết nối trong luồng nền; app sẽ thấy kết quả qua trạng thái."""
    a = load()["agents"].get(aid)
    if a is None:
        raise ValueError(f"Không có nhân viên '{aid}'")
    if providers.PRESETS[a["provider"]["type"]]["kind"] == "manual":
        raise ValueError("Nhân viên tự báo cáo, không kiểm tra tự động được")

    def job():
        set_status(aid, "waiting", "Đang kiểm tra kết nối…")
        try:
            reply = providers.check(a["provider"], get_secret(aid))
            record_use(aid, usage=getattr(reply, "usage", None))
            out = str(reply).strip()[:80]
            set_conn(aid, True, out)
            set_status(aid, "idle", "")
            log(aid, "Kết nối ổn, sẵn sàng làm việc ✅")
            import workers
            workers.retry_now(aid)
        except providers.QuotaError as e:
            set_conn(aid, True, "Đã kết nối nhưng hết token")
            go_sleep(aid, e.retry_after, str(e))
        except Exception as e:  # noqa: BLE001
            set_conn(aid, False, str(e))
            set_status(aid, "error", str(e)[:160])
            ask_login_if_needed(aid, str(e))

    threading.Thread(target=job, daemon=True).start()
    return {"ok": True}


# ---------- Phó sếp: lệnh thường trực ----------

# Phó sếp KHÔNG BAO GIỜ duyệt thay những thứ này, luôn phải hỏi sếp.
ALWAYS_ASK = re.compile(
    r"rm\s+-[a-z]*r[a-z]*f|remove-item\b.*-recurse|\bprune\b|push\s+(-f|--force)|--force-with-lease|drop\s+(table|database)"
    r"|\bmkfs\b|\bformat\s+[a-z]:|reset\s+--hard|truncate\s+table|shutdown|reboot|\bdd\s+if=", re.I)
POLICY_PRESETS = {
    "deploy": r"deploy|push|scp|ssh|rsync|docker|compose|systemctl|vercel|netlify|firebase",
}


def add_policy(d):
    text = str(d.get("text", "")).strip()
    if not text:
        raise ValueError("Ghi lại lời sếp dặn (VD: 'cứ deploy hết đi')")
    effect = d.get("effect", "approve")
    if effect not in ("approve", "deny"):
        raise ValueError("effect phải là approve hoặc deny")
    kinds = [k for k in d.get("kinds", ["write", "tool"]) if k in ("write", "tool")]
    if not kinds:
        raise ValueError("Chọn ít nhất một loại yêu cầu (sửa file / chạy lệnh)")
    pattern = str(d.get("pattern", "")).strip()
    if pattern:
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Mẫu lệnh không hợp lệ: {e}") from e
    hours = float(d.get("hours") or 0)
    with _lock:
        s = load()
        p = {"id": s["next_policy"], "text": text[:200], "effect": effect, "kinds": kinds,
             "agents": [a for a in d.get("agents", []) if a in s["agents"]],
             "depts": [x for x in d.get("depts", []) if x in s["depts"]],
             "pattern": pattern, "expires": now() + int(hours * 3600) if hours > 0 else 0,
             "on": True, "created": now(), "used": 0}
        s["policies"].append(p)
        s["next_policy"] += 1
        save(s)
    log(DEPUTY, f"Đã ghi lệnh của sếp #{p['id']}: “{p['text']}”", kind="policy")
    return p


def update_policy(pid, d):
    with _lock:
        s = load()
        p = next((x for x in s["policies"] if x["id"] == int(pid)), None)
        if p is None:
            raise ValueError("Không có lệnh này")
        if d.get("delete"):
            s["policies"].remove(p)
            msg = f"Đã xoá lệnh #{p['id']}: “{p['text']}”"
        else:
            p["on"] = bool(d.get("on", p["on"]))
            msg = f"{'Bật lại' if p['on'] else 'Tạm tắt'} lệnh #{p['id']}: “{p['text']}”"
        save(s)
    log(DEPUTY, msg, kind="policy")
    return {"ok": True}


def match_policy(s, agent, kind, text):
    if kind not in ("write", "tool") or ALWAYS_ASK.search(text):
        return None
    dept = s["agents"].get(agent, {}).get("dept")
    for p in s["policies"]:
        if not p["on"] or (p["expires"] and p["expires"] < now()) or kind not in p["kinds"]:
            continue
        if p["agents"] and agent not in p["agents"]:
            continue
        if p["depts"] and dept not in p["depts"]:
            continue
        if p["pattern"] and not re.search(p["pattern"], text, re.I):
            continue
        return p
    return None


# ---------- Thư ký: hàng đợi xin duyệt ----------

def request_approval(agent, kind, title, detail="", ref=""):
    """kind: write (cho quyền sửa file/chạy lệnh), tool (một lệnh cụ thể), login (cần sếp đăng nhập).

    Phó sếp xem lệnh thường trực trước; khớp thì quyết luôn, không thì Thư ký hỏi sếp.
    """
    with _lock:
        s = load()
        pol = match_policy(s, agent, kind, f"{title}\n{detail}")
        if pol:
            aid = f"a{now()}{len(s['approvals'])}"
            status = "approved" if pol["effect"] == "approve" else "denied"
            s["approvals"].append({"id": aid, "agent": agent, "kind": kind, "title": title, "detail": detail[:2000],
                                   "ref": ref, "status": status, "t": now(), "decided": now(), "by": DEPUTY,
                                   "policy": pol["id"]})
            pol["used"] += 1
            s["approvals"] = [a for a in s["approvals"] if a["status"] == "pending"] + \
                             [a for a in s["approvals"] if a["status"] != "pending"][-50:]
            save(s)
            log(DEPUTY, f"{'Duyệt' if status == 'approved' else 'Từ chối'} thay sếp theo lệnh #{pol['id']} "
                        f"“{pol['text']}”: {title}", kind="deputy")
            return aid
        dup = next((a for a in s["approvals"] if a["status"] == "pending" and a["agent"] == agent
                    and a["kind"] == kind and a["title"] == title), None)
        if dup:
            return dup["id"]
        aid = f"a{now()}{len(s['approvals'])}"
        s["approvals"].append({"id": aid, "agent": agent, "kind": kind, "title": title, "detail": detail[:2000],
                               "ref": ref, "status": "pending", "t": now(), "decided": 0})
        s["approvals"] = [a for a in s["approvals"] if a["status"] == "pending"] + \
                         [a for a in s["approvals"] if a["status"] != "pending"][-50:]
        save(s)
    log(SECRETARY, f"Sếp ơi, {title}", kind="ask")
    return aid


def ask_login_if_needed(agent_id, err):
    if "đăng nhập" not in err.lower():
        return
    a = load()["agents"].get(agent_id, {})
    hint = providers.PRESETS.get(a.get("provider", {}).get("type"), {}).get("login_hint", "")
    kind = providers.PRESETS.get(a.get("provider", {}).get("type"), {}).get("kind")
    what = "nhập API key (bấm vào nhân viên → 🗝️ Nhập API key)" if kind == "api" else "đăng nhập"
    request_approval(agent_id, "login", f"{a.get('name', agent_id)} cần sếp {what}", hint)


def get_approval(aid):
    return next((a for a in load()["approvals"] if a["id"] == aid), None)


def wait_approval(aid, timeout=3600):
    end = time.time() + timeout
    while time.time() < end:
        a = get_approval(aid)
        if a is None:
            return None
        if a["status"] != "pending":
            return a["status"] == "approved"
        time.sleep(2)
    return None  # hết giờ


def decide(aid, ok, note=""):
    with _lock:
        s = load()
        a = next((x for x in s["approvals"] if x["id"] == aid), None)
        if a is None or a["status"] != "pending":
            raise ValueError("Yêu cầu này không còn chờ duyệt")
        a.update(status="approved" if ok else "denied", decided=now(), by="boss", note=str(note)[:1500])
        save(s)
        agent = s["agents"].get(a["agent"], {})
    log(SECRETARY, f"Sếp đã {'duyệt ✅' if ok else 'từ chối ❌'}: {a['title']}", kind="ask")
    if ok and a["kind"] == "login" and agent and providers.PRESETS.get(agent["provider"]["type"], {}).get("kind") == "cli":
        providers.login(agent["provider"], agent["name"])
    if a["kind"] == "sign":  # sếp ký duyệt kết quả cuối của quy trình cấp bậc
        import workflow
        workflow.boss_signed(a, ok, note)
    if a["kind"] == "ask":  # sếp trả lời câu hỏi [CẦN SẾP]: việc chạy tiếp
        import workflow
        workflow.boss_answered(a, ok, note)
    return {"ok": True}


def kill_task(task_id=None, approval_id="", ask_path=""):
    """■ Dừng hẳn (ở ⏳ Chờ sếp): đóng mục chờ và dừng luôn việc, KHÔNG trả lại, KHÔNG làm tiếp."""
    s = load()
    a = next((x for x in s["approvals"] if x["id"] == approval_id), None) if approval_id else None
    if a and not task_id:
        ref = str(a.get("ref") or "")
        if ref.isdigit():
            task_id = int(ref)
        elif ref and (INBOX / ref).exists():  # xin quyền ghi/chạy lệnh: ref là tên thư, việc nằm trong thư
            task_id = parse_mail(INBOX / ref)[0].get("task") or None
    if ask_path:
        p = Path(ask_path)
        if p.exists():
            task_id = task_id or parse_mail(p)[0].get("task") or None
        _mark_ask(ask_path)
    t = get_task(task_id) if task_id else None
    if t and t["column"] != "done":
        set_task_fields(t["id"], stage="cancelled")
        move_task(t["id"], "done", actor="boss")  # huỷ thư còn chờ + dừng lượt đang chạy
    with _lock:  # đóng các mục chờ của việc này mà không gọi quy trình trả lại / làm tiếp
        s = load()
        for x in s["approvals"]:
            if x["status"] == "pending" and (x["id"] == approval_id or (t and str(x.get("ref")) == str(t["id"]))):
                x.update(status="denied", decided=now(), by="boss", note="Sếp dừng hẳn")
        save(s)
    title = t["title"] if t else (a or {}).get("title", "")
    which = f" việc #{t['id']}" if t else ""
    log("boss", f"■ Sếp dừng hẳn{which}: {title[:80]}", kind="task",
        to=(t or {}).get("owner") or (a or {}).get("agent"))
    return {"ok": True, "id": (t or {}).get("id")}


# ---------- Báo cáo công việc ngay ----------

STAGE_VN = {"assign": "trưởng phòng đang chia việc", "assigned": "đã chia việc", "work": "đang làm",
            "lead_review": "trưởng phòng đang duyệt", "deputy_review": "Phó sếp đang duyệt", "boss_sign": "chờ sếp ký",
            "done": "sếp đã ký"}


def _ago(ts):
    s = max(0, now() - int(ts or 0))
    return "vừa xong" if s < 60 else f"{s // 60} phút trước" if s < 3600 else f"{s // 3600} giờ trước"


def report():
    """Báo cáo ngắn từ dữ liệu văn phòng (không gọi model): mục tiêu, đang xử lý, chờ sếp, vướng, vừa xong."""
    s = load()
    A, T = s["agents"], s["tasks"]
    name = lambda k: "Sếp" if k == "boss" else A.get(k, {}).get("name", k or "chưa giao")  # noqa: E731
    by_id = {t["id"]: t for t in T}
    lines = [f"📋 Báo cáo lúc {datetime.now():%H:%M}"]

    # 🎯 mục tiêu: lệnh gốc chưa xong (không phải việc con)
    goals = [t for t in T if t["column"] != "done" and not t.get("parent") and not t["title"].startswith("📬")]
    small = [t for t in T if t["column"] == "review" and t["title"].startswith("📬")]
    lines.append("\n🎯 MỤC TIÊU ĐANG THEO ĐUỔI")
    if not goals:
        lines.append("- Không có lệnh nào đang mở.")
    for g in sorted(goals, key=lambda x: x.get("created", 0)):
        kids = [by_id[c] for c in g.get("children", []) if c in by_id]
        head = f"- #{g['id']} {g.get('request', g['title'])[:160]}"
        if kids:
            cnt = {}
            for k in kids:
                lab = "đã ký" if k.get("stage") == "done" else ("bị trả lại, đang làm lại" if k.get("rounds") and k.get("stage") == "work"
                                                                 else STAGE_VN.get(k.get("stage"), k["column"]))
                cnt[lab] = cnt.get(lab, 0) + 1
            head += f"\n    Tiến độ: {len(kids)} phần việc · " + ", ".join(f"{v} {k}" for k, v in cnt.items())
        else:
            head += f"\n    Trạng thái: {STAGE_VN.get(g.get('stage'), g['column'])} · phụ trách: {name(g['owner'])}"
        lines.append(head)

    # ⚙️ đang xử lý
    busy = [(k, a) for k, a in A.items() if a.get("status") == "working"]
    lines.append("\n⚙️ ĐANG XỬ LÝ NGAY LÚC NÀY")
    if not busy:
        lines.append("- Không ai đang làm.")
    for k, a in busy:
        mins = max(0, now() - int(a.get("since") or now())) // 60
        lines.append(f"- {a['name']}: {a.get('task', '')[:140]}" + (f"\n    → {a['step']}" if a.get("step") else "")
                     + f" ({mins} phút)")

    # ⏳ chờ sếp
    pend = [x for x in s["approvals"] if x["status"] == "pending"]
    asks = []
    for p in INBOX.glob("*.md"):
        if p.name.endswith((".done.md", ".denied.md")):
            continue
        meta, body = parse_mail(p)
        if meta.get("to") in ("thuky", "boss") or "_to_thuky_" in p.name:
            first = next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), p.stem)
            asks.append(f"- Thư từ {name(p.name.split('_')[2] if p.name.count('_') > 2 else '?')}: {first[:140]}")
    lines.append("\n⏳ ĐANG CHỜ SẾP")
    if not pend and not asks:
        lines.append("- Không có gì chờ sếp.")
    lines += [f"- {x['title'][:150]}" for x in pend] + asks
    if small:
        lines.append(f"- {len(small)} kết quả nhỏ chờ sếp xem rồi kéo sang Xong (bảng Công việc): "
                     + "; ".join(f"#{x['id']} {x['title'][2:60]}" for x in small[:4]) + ("…" if len(small) > 4 else ""))

    # ⚠️ vướng
    stuck = [(k, a) for k, a in A.items() if a.get("status") == "error" or a.get("sleep_until")]
    if stuck:
        lines.append("\n⚠️ ĐANG VƯỚNG")
        for k, a in stuck:
            lines.append(f"- {a['name']}: " + ("hết token, đang ngủ" if a.get("sleep_until") else a.get("task", "")[:150]))

    # ✅ vừa xong (2 giờ)
    recent = [e for e in recent_activity(300) if e.get("kind") in ("done", "review") and now() - e["t"] < 7200][:6]
    if recent:
        lines.append("\n✅ VỪA XONG (2 GIỜ QUA)")
        lines += [f"- {name(e['agent'])}: {e['text'][:140]} ({_ago(e['t'])})" for e in recent]
    return "\n".join(lines)


def report_ai():
    """Tóm tắt báo cáo bằng model nhẹ nhất đang dùng được (tốn 1 lượt)."""
    text, model = _light_ai("Bạn là trợ lý báo cáo cho sếp. Dựa CHỈ vào dữ liệu dưới đây, viết báo cáo tiếng Việt 4-6 câu ngắn: "
                            "văn phòng đang làm gì, mục tiêu là gì, đang xử lý tới đâu, sếp cần quyết gì. Không bịa thêm.",
                            report(), timeout=180)
    return {"text": text, "model": model}


def public_agents(s):
    sec = _secrets()
    out = {}
    for k, a in s["agents"].items():
        p = providers.PRESETS.get(a["provider"]["type"], {})
        out[k] = {**a, "has_key": bool(sec.get(k, {}).get("api_key")), "installed": providers.installed(a["provider"]),
                  "provider_label": p.get("label", "?"), "provider_kind": p.get("kind", "manual"),
                  "login_hint": p.get("login_hint", ""), "can_install": bool(p.get("install"))}
    return out


def _fix_stale_working(s):
    """Nhân viên tự động báo 'đang làm' mà không có lượt nào đang chạy thật → đưa về rảnh."""
    w = sys.modules.get("workers")
    if not w:
        return
    stale = [k for k, a in s["agents"].items() if a.get("status") == "working" and a.get("auto")
             and k not in w._busy and now() - int(a.get("since") or 0) > 20
             and not a.get("model_now")]  # đang chạy bằng công cụ ngoài (phản biện mù, thử đề): model_now còn đặt
    for k in stale:
        set_status(k, "idle", "")


# Bảng giá tham khảo (USD / 1 triệu token: vào, ra, cache) cho model mà CLI không báo tiền (vd Antigravity).
# Chỉ để quy đổi so sánh; sếp sửa được ở 📊 Token. Khớp theo đoạn tên model, đoạn dài hơn ưu tiên.
PRICE_DEFAULTS = {"gemini": (0.30, 2.50, 0.075), "claude-opus": (5.0, 25.0, 0.50), "opus": (5.0, 25.0, 0.50),
                  "claude-sonnet": (3.0, 15.0, 0.30), "sonnet": (3.0, 15.0, 0.30), "haiku": (1.0, 5.0, 0.10),
                  "fable": (5.0, 25.0, 0.50), "gpt-oss": (0.15, 0.60, 0.0), "gpt": (1.25, 10.0, 0.125)}


def price_of(model):
    """(vào, ra, cache, nguồn) cho một model: giá sếp đặt, không thì giá tham khảo."""
    own = (load().get("prices") or {}).get(model)
    if own:
        return (*own, "sếp đặt")
    key = next((k for k in sorted(PRICE_DEFAULTS, key=len, reverse=True) if k in model.lower()), None)
    return (*PRICE_DEFAULTS[key], "tham khảo") if key else None


def set_price(model, pin=None, pout=None, pcache=None):
    model = str(model).strip()
    if not model:
        raise ValueError("Thiếu tên model")
    with _lock:
        s = load()
        s.setdefault("prices", {})
        if pin in (None, "") and pout in (None, ""):
            s["prices"].pop(model, None)  # xoá giá tự đặt: quay về giá tham khảo
        else:
            s["prices"][model] = [float(pin or 0), float(pout or 0), float(pcache or 0)]
        save(s)
    return {"ok": True}


def snapshot():
    _fix_stale_working(load())
    s = load()
    agents = public_agents(s)
    pending = [a for a in s["approvals"] if a["status"] == "pending"]
    sec = agents.get(SECRETARY)
    if sec:  # Thư ký phản ánh hàng đợi duyệt
        if pending:
            sec.update(status="waiting", task=f"Sếp ơi, có {len(pending)} việc cần duyệt!", since=min(a["t"] for a in pending))
        else:
            sec.update(status="idle", task="Em trực quầy, chưa có gì cần duyệt ☕")
    dep = agents.get(DEPUTY)
    live = [p for p in s["policies"] if p["on"] and not (p["expires"] and p["expires"] < now())]
    if dep and dep["status"] not in ("working", "error") and not dep.get("sleep_until"):
        recent = [a for a in s["approvals"] if a.get("by") == DEPUTY and now() - a["decided"] < 120]
        if recent:
            dep.update(task=f"Vừa duyệt thay sếp: {recent[-1]['title']}")  # chỉ ghi chú, không coi là đang làm
        else:
            dep.update(status="idle", task=f"Đang giữ {len(live)} lệnh của sếp 📜" if live else "Sếp chưa dặn gì")
    return {"agents": agents, "depts": s["depts"], "tasks": s["tasks"], "activity": recent_activity(),
            "inbox": inbox_items(), "t": now(), "approvals": pending,
            "decided": [a for a in s["approvals"] if a["status"] != "pending"][-8:],
            "policies": s["policies"], "policy_presets": POLICY_PRESETS, "skills": list_skills(),
            "quota": quota_status(s), "charter": s.get("charter", []), "sys": sysmon.stats(),
            "waiting_count": (lambda w: len(w["approvals"]) + len(w["asks"]) + len(w["results"]))(waiting()),
            "issues_count": issues_count(),
            "tokens": {"all": s.get("tokens", {}), "today": s.get("tokens_day", {}).get(datetime.now().strftime("%Y-%m-%d"), {}),
                       "days": {d: sum(m["in"] + m["out"] + m["cache"] for m in v.values())
                                for d, v in s.get("tokens_day", {}).items()}},
            "presets": {k: {"label": v["label"], "kind": v["kind"]} for k, v in providers.PRESETS.items()},
            "hats": HATS, "phases": PHASES,
            "prices": {m: price_of(m) for m in (s.get("tokens") or {})}}


# ---------- CLI ----------

def cmd_status(a):
    set_status(a.agent, a.status, a.task or "")


def cmd_log(a):
    log(a.agent, a.text)


def cmd_task(a):
    if a.action == "add":
        print(add_task(a.arg, a.owner, a.phase)["id"])
    else:
        move_task(a.arg, a.column)


def cmd_mail(a):
    print(send_mail(a.frm, a.to, a.kind, a.subject, a.body, a.input, a.output, a.mode, a.workdir))


# ---------- HTTP ----------

LOCAL = re.compile(r"^(localhost|127\.0\.0\.1)(:\d+)?$")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kw):
        super().__init__(*args, directory=str(APP), **kw)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")  # sửa app xong chỉ cần tải lại trang
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _local(self):
        # Chặn DNS rebinding và trang web lạ gọi vào localhost
        host_ok = LOCAL.match(self.headers.get("Host", ""))
        origin = self.headers.get("Origin", "")
        return host_ok and (not origin or re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin))

    def do_GET(self):
        if not self._local():
            return self._json(403, {"error": "chỉ dùng trên máy này"})
        if self.path.startswith("/api/state"):
            return self._json(200, snapshot())
        if self.path.startswith("/api/issues"):
            import troubleshoot
            return self._json(200, troubleshoot.diagnose())
        if self.path.startswith("/api/tester/list"):
            return self._json(200, tester_list())
        if self.path.startswith("/api/waiting"):
            return self._json(200, waiting())
        if self.path.startswith("/api/report"):
            return self._json(200, {"text": report()})
        if self.path.startswith("/api/output/"):  # kết quả của một thẻ việc (để sếp đọc trước khi ký)
            t = get_task(self.path[len("/api/output/"):].split("?")[0])
            p = (ROOT / t["output"]).resolve() if t and t.get("output") else None
            if not p or not p.exists() or (ROOT / "outputs").resolve() not in p.parents:
                return self._json(404, {"error": "chưa có kết quả"})
            return self._json(200, {"file": t["output"], "text": p.read_text(encoding="utf-8", errors="replace"),
                                    "history": t.get("history", [])})
        if self.path.startswith("/api/mail/"):
            p = INBOX / Path(unquote(self.path[len("/api/mail/"):])).name
            if not p.exists():
                return self._json(404, {"error": "không thấy thư"})
            return self._json(200, {"file": p.name, "text": p.read_text(encoding="utf-8")})
        super().do_GET()

    def do_POST(self):
        if not self._local() or "application/json" not in self.headers.get("Content-Type", ""):
            return self._json(403, {"error": "chỉ dùng trên máy này"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n) or b"{}")
            route = self.path.split("?")[0]
            routes = {
                "/api/room/command": lambda: room_command(d["dept"], d.get("text", ""), d.get("mode", "read"), d.get("flow", "full"),
                                                          d.get("deliver", "show")),
                "/api/task/result": lambda: task_result(d["id"]),
                "/api/task/openfiles": lambda: open_files(d["id"]),
                "/api/agent/perm": lambda: set_perm(d["id"], d["perm"], bool(d.get("on"))),
                "/api/term/start": lambda: term_start(d.get("cmd", ""), d.get("cwd", ""), d.get("shell", "bash")),
                "/api/term/poll": lambda: term_poll(d["id"], bool(d.get("stop"))),
                "/api/tester/run": lambda: tester_run(d["where"], d["slug"]),
                "/api/tester/deploy": lambda: tester_deploy(d["where"], d["slug"], bool(d.get("publish"))),
                "/api/agent/stop": lambda: stop_agent(d["id"]),
                "/api/dept/stop": lambda: stop_dept(d["dept"]),
                "/api/task/archive": lambda: archive_tasks(d.get("ids"), bool(d.get("done"))),
                "/api/task/kill": lambda: kill_task(d.get("id"), d.get("approval", ""), d.get("path", "")),
                "/api/task/grant": lambda: grant_task(d["id"], d.get("approval", ""), bool(d.get("cmds"))),
                "/api/dept/summary": lambda: dept_summary(d["dept"]),
                "/api/quota": lambda: set_quota(d["account"], d.get("window_h"), d.get("limit"), d.get("week")),
                "/api/task/add": lambda: dispatch_task(d["title"], d.get("phase", "idea"), d.get("owner", "auto"),
                                                       d.get("dept", ""), d.get("body", ""), d.get("mode", "read"),
                                                       bool(d.get("run", True)), d.get("inputs", [])),
                "/api/task/move": lambda: move_task(d["id"], d["column"], actor="boss"),
                "/api/task/update": lambda: update_task(d["id"], actor="boss", title=d.get("title"), owner=d.get("owner"),
                                                        phase=d.get("phase"), delete=d.get("delete")),
                "/api/status": lambda: set_status(d["agent"], d["status"], d.get("task", "")) or {"ok": True},
                "/api/mail": lambda: {"file": send_mail("boss", d["to"], d.get("kind", "task"), d["subject"].strip(),
                                                        d.get("body", ""), d.get("inputs", []), d.get("output", ""),
                                                        d.get("mode", "read"), d.get("workdir", ""))},
                "/api/agent/add": lambda: add_agent(d),
                "/api/agent/update": lambda: update_agent(d["id"], d),
                "/api/agent/remove": lambda: remove_agent(d["id"]),
                "/api/agent/key": lambda: set_secret(d["id"], d.get("api_key", "").strip()) or {"ok": True},
                "/api/agent/check": lambda: check_agent(d["id"]),
                "/api/agent/login": lambda: self._agent_action(d["id"], providers.login),
                "/api/agent/install": lambda: self._agent_action(d["id"], providers.install),
                "/api/dept/add": lambda: add_dept(d["name"], d.get("icon", "🏠"), d.get("workdir", ""), d.get("notes", "")),
                "/api/dept/update": lambda: update_dept(d["id"], d),
                "/api/approval/decide": lambda: decide(d["id"], bool(d["ok"]), d.get("note", "")),
                "/api/report/ai": report_ai,
                "/api/ask/reply": lambda: ask_reply(d["path"], d.get("text", "")),
                "/api/ask/dismiss": lambda: ask_dismiss(d["path"]),
                "/api/issues/fix": lambda: __import__("troubleshoot").fix(d["id"], d["action"], d.get("text", ""), d.get("to", "")),
                "/api/charter/add": lambda: charter_add(d.get("text", "")),
                "/api/charter/update": lambda: charter_update(d["id"], d),
                "/api/agent/models": lambda: {"models": self._models(d)},
                "/api/price": lambda: set_price(d["model"], d.get("in"), d.get("out"), d.get("cache")),
                "/api/policy/add": lambda: add_policy(d),
                "/api/policy/update": lambda: update_policy(d["id"], d),
                "/api/dept/remove": lambda: remove_dept(d["id"], d.get("move_to")),
                "/api/shutdown": shutdown_server,
                "/api/pack": pack,
                "/api/shortcut": make_shortcut,
            }
            if route not in routes:
                return self._json(404, {"error": "không có API này"})
            return self._json(200, routes[route]() or {"ok": True})
        except (KeyError, ValueError, RuntimeError) as e:
            return self._json(400, {"error": str(e)})

    @staticmethod
    def _models(d):
        # provider có thể là cấu hình đang sửa (chưa lưu) trong hồ sơ
        prov = _clean_provider(d.get("provider") or load()["agents"].get(d.get("id", ""), {}).get("provider", {}))
        return providers.list_models(prov, get_secret(d.get("id", "")))

    @staticmethod
    def _agent_action(aid, fn):
        a = load()["agents"].get(aid)
        if a is None:
            raise ValueError(f"Không có nhân viên '{aid}'")
        fn(a["provider"], a["name"])
        return {"ok": True}


# ---------- chia sẻ: shortcut + đóng gói ----------

SHORTCUT_NAME = "Văn phòng ResearchLab.lnk"
PACK_SKIP_DIRS = {"state", "inbox", "outputs", "dist", "__pycache__", ".claude", ".git"}


def make_shortcut():
    """Tạo shortcut trên Desktop chạy app không kèm cửa sổ đen (Windows)."""
    import base64
    import subprocess
    if os.name != "nt":
        raise ValueError("Shortcut chỉ hỗ trợ Windows")
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else sys.executable)
    tmp_name = "ResearchLab-shortcut-tmp.lnk"  # WScript làm rơi chữ "ă": tạo tên không dấu rồi đổi tên
    ps = (
        "$d=[Environment]::GetFolderPath('Desktop');Write-Output $d;"
        "$l=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '" + tmp_name + "'));"
        f"$l.TargetPath='{exe}';"
        f"$l.Arguments='\"{ROOT / 'tools' / 'office.py'}\" serve --open';"
        f"$l.WorkingDirectory='{ROOT}';"
        "$l.IconLocation=\"$env:SystemRoot\\System32\\imageres.dll,104\";"
        "$l.Description='Mo van phong ResearchLab';$l.Save()"
    )
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc], check=True, capture_output=True,
                       text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    desk = Path(r.stdout.strip().splitlines()[0])
    os.replace(desk / tmp_name, desk / SHORTCUT_NAME)  # ghi đè shortcut cũ cùng tên, không sinh thêm
    for stray in desk.glob("Van ph*ResearchLab.lnk"):  # bản sai tên từ lần trước
        if stray.name != SHORTCUT_NAME:
            stray.unlink()
    (STATE.parent / ".shortcut").write_text(str(ROOT), encoding="utf-8")
    return {"ok": True}


def ensure_shortcut():
    flag = STATE.parent / ".shortcut"
    if os.name == "nt" and not (flag.exists() and flag.read_text(encoding="utf-8") == str(ROOT)):
        try:
            make_shortcut()
            log("boss", "Đã tạo shortcut trên Desktop 📌", kind="status")
        except Exception as e:  # noqa: BLE001
            print("Không tạo được shortcut:", e)


def pack():
    """Đóng gói app để chia sẻ: chỉ code + quy tắc + khung, KHÔNG kèm dữ liệu riêng hay API key."""
    import zipfile
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"ResearchLab-{datetime.now():%Y%m%d-%H%M}.zip"
    private_skills = {k["id"] for k in list_skills() if k["private"]}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            rel = p.relative_to(ROOT)
            if rel.parts[0] in PACK_SKIP_DIRS or "__pycache__" in rel.parts or p.suffix in (".log", ".tmp"):
                continue
            if rel.parts[0] == "projects" and len(rel.parts) > 1 and rel.parts[1] != "_template":
                continue  # project riêng của mình
            if rel.parts[0] == "skills" and len(rel.parts) > 1 and rel.parts[1] in private_skills:
                continue  # skill riêng tư (đường dẫn, nội dung paper của sếp)
            if p.is_file():
                z.write(p, Path("ResearchLab") / rel)
            elif not any(p.iterdir()):  # giữ thư mục rỗng (khung project)
                z.writestr((Path("ResearchLab") / rel).as_posix() + "/", "")
        for d in ("inbox", "outputs", "state"):
            z.writestr(f"ResearchLab/{d}/", "")
    log("boss", f"Đóng gói chia sẻ: {out.name} 📦", kind="status")
    if os.name == "nt":
        import subprocess
        subprocess.Popen(["explorer", "/select,", str(out)])
    return {"file": str(out)}


_server = None


def shutdown_server():
    """Nút ⏻ trên app: tắt server sau khi đã trả lời request."""
    log("boss", "Tắt văn phòng ⏻", kind="status")
    threading.Timer(0.3, _server.shutdown).start()
    return {"ok": True}


def open_app_window(url):
    """Mở app bằng Firefox (ưu tiên, theo ý sếp); không có thì Edge/Chrome chế độ cửa sổ app; cuối cùng trình duyệt mặc định."""
    import subprocess
    import webbrowser
    firefox = [os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
               os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
               os.path.expandvars(r"%LocalAppData%\Mozilla Firefox\firefox.exe")]
    chromium = [os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")]
    ff = next((c for c in firefox if os.path.exists(c)), None)
    cr = next((c for c in chromium if os.path.exists(c)), None)
    if ff:
        subprocess.Popen([ff, "-new-window", url])  # F11 để toàn màn hình
    elif cr:
        subprocess.Popen([cr, f"--app={url}", "--start-maximized"])
    else:
        webbrowser.open(url)


def already_running(port):
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def cmd_serve(a):
    global _server
    url = f"http://localhost:{a.port}"
    if already_running(a.port):  # đã mở rồi: chỉ mở lại trang
        if a.open:
            open_app_window(url)
        print(f"Văn phòng đang chạy sẵn: {url}")
        return
    with _lock:
        s = load()
        for k, ag in s["agents"].items():  # lần chạy trước bị tắt giữa chừng: không ai còn "đang làm" thật
            if ag.get("status") == "working" or ag.get("task") == "Đang kiểm tra kết nối…":
                ag.update(status="idle", task="", since=now())
        save(s)
    sysmon.start()  # CPU / RAM / GPU cho thanh trạng thái
    if not a.no_workers:
        import workers
        threading.Thread(target=workers.watch, daemon=True).start()
        print("Nhân viên tự động sẽ tự nhận thư trong inbox/")
    _server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"ResearchLab office: {url}")
    log("boss", "Mở văn phòng ☀️", kind="status")
    if a.open:
        ensure_shortcut()  # lần đầu chạy trên máy mới: tạo shortcut Desktop
        threading.Timer(0.5, open_app_window, args=(url,)).start()
    _server.serve_forever()


def main():
    if sys.stdout is None:  # chạy bằng pythonw (không có cửa sổ): ghi ra file log
        STATE.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(STATE.parent / "server.log", "a", encoding="utf-8", buffering=1)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="ResearchLab office")
    sub = p.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("status")
    x.add_argument("agent")
    x.add_argument("status", choices=STATUSES)
    x.add_argument("task", nargs="?", default="")
    x.set_defaults(fn=cmd_status)

    x = sub.add_parser("log")
    x.add_argument("agent")
    x.add_argument("text")
    x.set_defaults(fn=cmd_log)

    x = sub.add_parser("task")
    x.add_argument("action", choices=("add", "move"))
    x.add_argument("arg", help="tiêu đề (add) hoặc id (move)")
    x.add_argument("column", nargs="?", default="todo")
    x.add_argument("--owner", default="")
    x.add_argument("--phase", default="idea", choices=PHASES)
    x.set_defaults(fn=cmd_task)

    x = sub.add_parser("mail", help="gửi thư giao việc")
    x.add_argument("frm", metavar="from")
    x.add_argument("to")
    x.add_argument("kind", choices=MAIL_KINDS)
    x.add_argument("subject")
    x.add_argument("--body", default="")
    x.add_argument("--input", action="append", default=[], help="file đầu vào (lặp lại được)")
    x.add_argument("--output", default="", help="file kết quả, tương đối với ResearchLab")
    x.add_argument("--mode", default="read", choices=("read", "write"), help="write = được sửa file (cần sếp duyệt)")
    x.add_argument("--workdir", default="", help="thư mục làm việc (mặc định: thư mục của phòng)")
    x.set_defaults(fn=cmd_mail)

    x = sub.add_parser("pack", help="đóng gói app để chia sẻ (không kèm dữ liệu riêng)")
    x.set_defaults(fn=lambda a: print(pack()["file"]))

    x = sub.add_parser("shortcut", help="tạo shortcut trên Desktop")
    x.set_defaults(fn=lambda a: make_shortcut())

    x = sub.add_parser("serve")
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--no-workers", action="store_true", help="không cho nhân viên tự nhận thư")
    x.add_argument("--open", action="store_true", help="mở trình duyệt khi chạy")
    x.set_defaults(fn=cmd_serve)

    a = p.parse_args()
    try:
        a.fn(a)
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
