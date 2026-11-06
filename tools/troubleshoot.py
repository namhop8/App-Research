"""Xử lý sự cố: văn phòng tự dò sự cố, đưa ra cách xử lý; sếp chọn cách hoặc ghi chỉ đạo riêng.

    diagnose()  → danh sách sự cố, mỗi sự cố có các lựa chọn xử lý
    fix(id, action, text, to)  → làm theo lựa chọn của sếp
"""
import hashlib
from pathlib import Path

import office
import providers
import workflow

LOOP_ROUNDS = 2        # bị trả lại từ chừng này lần là "quay vòng"
STALE_SECONDS = 3600   # thẻ việc đứng im quá lâu
ASK_SECONDS = 600      # câu hỏi của nhân viên chưa ai trả lời

A = lambda key, label: {"key": key, "label": label}  # noqa: E731


def _iid(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _pending_mails(agent_id=None, task_id=None):
    out = []
    for p in office.INBOX.glob("*.md"):
        if p.name.endswith((".done.md", ".denied.md")):
            continue
        meta, _ = office.parse_mail(p)
        to = meta.get("to") or office._route_from_name(p.name).get("to")
        if agent_id and to != agent_id:
            continue
        if task_id is not None and str(meta.get("task", "")) != str(task_id):
            continue
        out.append(p)
    return out


def _others(dept, exclude):
    s = office.load()
    return [k for k, a in s["agents"].items() if a["dept"] == dept and k != exclude and not a.get("system") and workflow.usable(k)]


def diagnose():
    s = office.load()
    A_, now = s["agents"], office.now()
    issues = []

    # 1) nhân viên đang lỗi
    for k, a in A_.items():
        if a.get("status") == "error":
            n = len(_pending_mails(k))
            err = a.get("task", "")
            read_denied = "read_file" in err or "permission" in err.lower()
            opts = [A("clear", "✅ Xoá báo lỗi (không còn việc chờ)")] if n == 0 else []
            if read_denied:
                opts.append(A("grant_dir", "📂 Cấp thêm thư mục rồi thử lại"))
            opts += [A("retry", "🔄 Thử lại ngay"), A("check", "🩺 Kiểm tra kết nối")]
            if providers.PRESETS.get(a["provider"]["type"], {}).get("kind") == "cli":
                opts.append(A("login", "🔑 Đăng nhập lại"))
            if n and _others(a["dept"], k):
                opts.append(A("reassign_agent", f"👤 Giao {n} việc đang chờ cho người khác"))
            why = ("Bị chặn đọc file: file nằm ngoài các thư mục nhân viên được phép vào. "
                   "Cấp thêm thư mục chứa file đó (vd. D:\\Paper3) rồi thử lại.\n") if read_denied else ""
            issues.append({"id": _iid("err", k, a.get("since")), "kind": "agent_error", "agent": k,
                           "severity": "cao" if n else "thấp",
                           "title": f"{a['name']} đang gặp sự cố" + ("" if n else " (báo lỗi cũ, không còn việc chờ)"),
                           "detail": f"{why}Lỗi: {err[:300]}\nĐang có {n} thư chờ làm.", "options": opts,
                           "dir_input": read_denied})

    # 2) hết token mà còn việc chờ
    for k, a in A_.items():
        if (a.get("sleep_until") or 0) > now and _pending_mails(k):
            opts = [A("wake", "⏰ Đánh thức thử")]
            if _others(a["dept"], k):
                opts.append(A("reassign_agent", "👤 Giao việc đang chờ cho người khác"))
            issues.append({"id": _iid("sleep", k, a["sleep_until"]), "kind": "sleep", "agent": k, "severity": "vừa",
                           "title": f"{a['name']} hết token, còn việc chờ",
                           "detail": f"Ngủ tới {office.datetime.fromtimestamp(a['sleep_until']):%H:%M}.", "options": opts})

    # 3) việc quay vòng (bị trả lại nhiều lần)
    for t in s["tasks"]:
        if t.get("stage") in ("work", "lead_review", "deputy_review") and t.get("rounds", 0) >= LOOP_ROUNDS:
            last = (t.get("history") or [{}])[-1]
            opts = [A("to_boss", "✒️ Đưa thẳng lên sếp quyết"), A("stop", "🛑 Dừng việc này")]
            if _others(t.get("dept", ""), t["owner"]):
                opts.append(A("reassign_task", "👤 Giao cho người khác"))
            issues.append({"id": _iid("loop", t["id"], t.get("rounds")), "kind": "loop", "task": t["id"], "agent": t["owner"],
                           "severity": "cao", "title": f"Việc #{t['id']} bị trả lại {t['rounds']} lần",
                           "detail": f"{t['title']}\nNgười làm: {A_.get(t['owner'], {}).get('name', t['owner'])}"
                                     f"\nLần trả lại gần nhất ({last.get('who', '?')}): {last.get('note', '')[:400]}",
                           "options": opts, "direct": True})

    # 4) việc đứng im
    busy = {a.get("task", "") for a in A_.values() if a.get("status") == "working"}
    for t in s["tasks"]:
        if t["column"] in ("doing", "todo") and t.get("stage") not in ("boss_sign", "done", "assigned") \
                and now - t.get("updated", now) > STALE_SECONDS and not any(t["title"][:30] in b for b in busy) \
                and not t["title"].startswith("📬"):
            issues.append({"id": _iid("stale", t["id"], t.get("updated")), "kind": "stale", "task": t["id"], "agent": t["owner"],
                           "severity": "thấp", "title": f"Việc #{t['id']} đứng im {(now - t['updated']) // 3600} giờ",
                           "detail": t["title"], "options": [A("redo", "🔄 Giao làm lại"), A("stop", "🛑 Dừng / đóng việc")],
                           "direct": True})

    # 5) câu hỏi của nhân viên chưa trả lời
    old = [x for x in office.waiting()["asks"] if now - x["t"] > ASK_SECONDS]
    if old:
        issues.append({"id": _iid("asks", len(old), old[0]["t"]), "kind": "asks", "severity": "cao",
                       "title": f"{len(old)} câu hỏi / xin phép của nhân viên chưa được trả lời",
                       "detail": "\n".join(f"- {office.load()['agents'].get(x['from'], {}).get('name', x['from'])}: {x['subject'][:90]}"
                                           for x in old[:6]),
                       "options": [A("open_waiting", "💬 Mở mục Chờ sếp để trả lời")]})
    order = {"cao": 0, "vừa": 1, "thấp": 2}
    return sorted(issues, key=lambda i: order.get(i["severity"], 3))


def _deny_mails(paths):
    for p in paths:
        try:
            p.rename(p.with_name(p.name[:-3] + ".denied.md"))
        except OSError:
            pass


def fix(issue_id, action, text="", to=""):
    issue = next((i for i in diagnose() if i["id"] == issue_id), None)
    if issue is None:
        raise ValueError("Sự cố này đã hết hoặc đã được xử lý")
    agent, task_id, text = issue.get("agent"), issue.get("task"), (text or "").strip()
    note = f" Chỉ đạo của sếp: {text}" if text else ""
    s = office.load()
    who = s["agents"].get(agent, {}).get("name", agent)

    if action == "clear":
        office.set_status(agent, "idle", "")
        msg = f"Xoá báo lỗi của {who}"
    elif action == "grant_dir":
        if not text or not Path(text).is_dir():
            raise ValueError("Gõ đường dẫn một thư mục có thật trên máy (vd. D:\\Paper3)")
        dept = s["agents"][agent]["dept"]
        cur = s["depts"][dept].get("dirs", [])
        office.update_dept(dept, {"dirs": cur + [text] if text not in cur else cur})
        office.set_status(agent, "idle", "")
        try:
            import workers
            workers.retry_now(agent)
        except Exception:  # noqa: BLE001
            pass
        msg = f"Cấp thư mục {text} cho {s['depts'][dept]['name']}, cho {who} thử lại"
        note = ""
    elif action in ("retry", "wake"):
        office.set_status(agent, "idle", "")
        office.set_conn(agent, None, "")
        try:
            import workers
            workers.retry_now(agent)
        except Exception:  # noqa: BLE001
            pass
        msg = f"Cho {who} thử lại"
    elif action == "check":
        office.check_agent(agent)
        msg = f"Kiểm tra kết nối của {who}"
    elif action == "login":
        a = s["agents"][agent]
        providers.login(a["provider"], a["name"])
        msg = f"Mở cửa sổ đăng nhập cho {who}"
    elif action == "reassign_agent":
        dept = s["agents"][agent]["dept"]
        target = to or (_others(dept, agent) or [None])[0]
        if not target:
            raise ValueError("Không có ai trong phòng làm thay được")
        moved = 0
        for p in _pending_mails(agent):
            meta, body = office.parse_mail(p)
            tid = meta.get("task")
            if tid:
                office.set_task_fields(tid, owner=target)
            office.send_mail("boss", target, meta.get("kind", "task") if meta.get("kind") in office.MAIL_KINDS else "task",
                             meta.get("subject") or office._first_line(body) or p.stem,
                             (body + (f"\n\n{note}" if note else "")), meta.get("inputs") or (), meta.get("output", ""),
                             meta.get("mode", "read"), meta.get("workdir", ""), task_id=tid, stage=meta.get("stage", ""),
                             reason=f"sếp chuyển việc từ {who} sang {s['agents'][target]['name']} (🛠️ Sự cố)")
            _deny_mails([p])
            moved += 1
        office.set_status(agent, "idle", "")
        msg = f"Giao {moved} việc của {who} cho {s['agents'][target]['name']}"
    elif action == "to_boss":
        _deny_mails(_pending_mails(task_id=task_id))
        workflow._to_boss(task_id, "Sếp kéo lên xử lý vì việc quay vòng." + note)
        msg = f"Đưa việc #{task_id} lên sếp quyết"
    elif action == "stop":
        _deny_mails(_pending_mails(task_id=task_id))
        office.set_task_fields(task_id, stage="cancelled")
        office.move_task(task_id, "done", actor="boss")
        msg = f"Dừng việc #{task_id}"
    elif action in ("reassign_task", "redo", "direct"):
        t = office.get_task(task_id)
        target = t["owner"]
        if action == "reassign_task":
            target = to or (_others(t.get("dept", ""), t["owner"]) or [None])[0]
            if not target:
                raise ValueError("Không có ai trong phòng làm thay được")
        if action == "direct" and not text:
            raise ValueError("Ghi chỉ đạo của sếp trước đã")
        _deny_mails(_pending_mails(task_id=task_id))
        office.set_task_fields(task_id, owner=target, stage="work", rounds=0)
        body = (f"{'📌 CHỈ ĐẠO CỦA SẾP: ' + text if text else 'Sếp giao làm lại việc này.'}\n\n## Yêu cầu\n{t.get('request', t['title'])}"
                f"\n\n## Các lần duyệt trước\n{workflow._history_text(t)}\n\n## Kết quả lần trước\n{workflow._read(t.get('output'))}")
        workflow._send_work(task_id, body, frm="boss",
                            reason=f"sếp xử lý ở 🛠️ Sự cố: {'giao cho ' + s['agents'][target]['name'] if action == 'reassign_task' else 'giao làm lại'}"
                            + (f", chỉ đạo: {text[:80]}" if text else ""))
        msg = (f"Giao việc #{task_id} cho {s['agents'][target]['name']}" if action == "reassign_task"
               else f"Gửi chỉ đạo cho {s['agents'][target]['name']} làm lại #{task_id}")
    elif action == "open_waiting":
        return {"ok": True, "open": "waiting"}
    else:
        raise ValueError("Cách xử lý không hợp lệ")
    office.log("boss", f"🛠️ Xử lý sự cố: {msg}.{note}", kind="hr")
    return {"ok": True, "msg": msg}
