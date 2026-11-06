"""Quy trình cấp bậc (tôn ti trật tự) cho các phòng bật `workflow` và có trưởng phòng `head`.

    Sếp ra lệnh → Trưởng phòng chia việc ([GIAO @Tên] …)
      → Nhân viên làm → Trưởng phòng duyệt lần 1 → Phó sếp duyệt lần 2 → Sếp ký duyệt
    Ở bước duyệt nào chưa đạt ([CHƯA ĐẠT] vấn đề…) thì trả về nhân viên làm lại, kèm vấn đề cụ thể.
    Trả lại quá MAX_ROUNDS lần thì đưa thẳng lên sếp quyết.

Mỗi bước là một thư trong inbox/ có `stage:` và `task:`; workers.py gọi after() khi nhân viên làm xong thư đó.
"""
import re
from pathlib import Path

import office

MAX_ROUNDS = 2  # trả lại quá chừng này lần thì sếp quyết (đỡ đốt quota)
ASSIGN = re.compile(r"^\s*\[GIAO\s+@([^\]\s]+)\]\s*(.+)$", re.M)
VERDICT = re.compile(r"\[(DUYỆT|CHƯA ĐẠT|CẦN SẾP)\]\s*(.*)", re.S)
NEED_BOSS = re.compile(r"^\s*\[CẦN SẾP\]\s*(.+)", re.M | re.S)
STAGE_TEXT = {"blind_test": "Mò đang thử mù", "assign": "trưởng phòng đang chia việc", "assigned": "đã chia việc", "work": "đang làm",
              "lead_review": "trưởng phòng duyệt", "deputy_review": "Phó sếp duyệt", "boss_sign": "chờ sếp ký",
              "done": "sếp đã ký"}

ASSIGN_PROMPT = (
    "Bạn là TRƯỞNG PHÒNG. Sếp vừa giao một việc cho phòng. Đừng tự làm hết: lập kế hoạch ngắn (2-3 câu) rồi chia thành "
    "các việc nhỏ cụ thể, giao cho đúng người trong phòng theo vai trò. Mỗi việc một dòng, đúng định dạng:\n"
    "[GIAO @Tên] <việc cụ thể, đầu vào, đầu ra mong muốn, tiêu chí đạt>\n"
    "Có thể giao cho chính mình nếu hợp vai. Chỉ dùng tên có trong danh sách nhân viên. Trả lời bằng tiếng Việt.\n"
    "CHIA ÍT NGƯỜI NHẤT CÓ THỂ: việc một người làm được thì giao đúng 1 người. Chỉ chia khi việc cần nhiều chuyên môn "
    "khác nhau hoặc các phần làm song song được; tối đa 3 người, các phần không chồng lên nhau.")
APPROVE_PROMPT = (
    "Bạn là NGƯỜI DUYỆT. Đối chiếu kết quả với yêu cầu, nội quy của sếp và quy định phòng. Nhận xét ngắn gọn, "
    "rồi kết thúc bằng ĐÚNG MỘT dòng cuối cùng:\n[DUYỆT] <một câu tóm tắt vì sao đạt>\nhoặc\n"
    "[CHƯA ĐẠT] <các vấn đề cụ thể, đánh số, mỗi vấn đề kèm cách sửa>\n"
    "hoặc, nếu chỗ chưa đạt là thứ người làm KHÔNG tự xử lý được (thiếu quyền chạy lệnh/ghi file, thiếu dữ liệu, "
    "tiêu chí không làm nổi, cần sếp chọn phương án):\n[CẦN SẾP] <câu hỏi ngắn cho sếp + các phương án>\n"
    "Đừng trả lại người làm vì những thứ họ không tự xử lý được.\n"
    "Không duyệt xã giao, nhưng cũng không bắt bẻ chuyện vụn vặt. Trả lời bằng tiếng Việt.\n"
    "DUYỆT GỌN: kết quả cần duyệt đã nằm trong thư. Chỉ mở thêm file khi phải kiểm chứng một điểm nghi ngờ cụ thể "
    "(tối đa vài file), KHÔNG chạy lệnh terminal, KHÔNG duyệt lại toàn bộ dự án. Nhận xét tối đa ~15 dòng.")


def _dept(dept_id):
    return office.load()["depts"].get(dept_id, {})


def usable(aid):
    """Nhân viên làm được ngay: tự động, đã cài, không lỗi kết nối, không ngủ."""
    agents = office.load()["agents"]
    a = agents.get(aid)
    if not a or not a.get("auto"):
        return False
    conn = a.get("conn", {})
    if conn.get("ok") is None:  # chưa kiểm tra riêng: dùng kết quả mới nhất của người cùng tài khoản
        same = [x.get("conn", {}) for x in agents.values()
                if x.get("provider", {}).get("type") == a["provider"]["type"] and x.get("conn", {}).get("ok") is not None]
        conn = max(same, key=lambda c: c.get("t", 0), default={})
    return (conn.get("ok") is not False and a["status"] != "error" and not a.get("sleep_until")
            and office.providers.installed(a["provider"]))


def acting(dept_id, wanted, exclude=()):
    """Người thực sự nhận việc: `wanted` nếu làm được, không thì người làm được trong phòng (quyền trưởng phòng)."""
    if usable(wanted):
        return wanted, ""
    s = office.load()
    cands = [k for k, a in s["agents"].items() if a["dept"] == dept_id and not a.get("system") and k not in exclude and usable(k)]
    if not cands:
        return wanted, ""  # không ai thay được: để nguyên, Thư ký sẽ xin sếp đăng nhập
    sub = cands[0]
    return sub, f"{_name(wanted)} chưa làm được (chưa đăng nhập / lỗi / hết token), {_name(sub)} làm thay"


def head_of(dept_id):
    """Trưởng phòng đang tại vị (hoặc quyền trưởng phòng)."""
    return acting(dept_id, _dept(dept_id).get("head"))


def enabled(dept_id):
    d = _dept(dept_id)
    return bool(d.get("workflow") and d.get("head") in office.load()["agents"])


def _name(aid):
    return office.load()["agents"].get(aid, {}).get("name", aid)


def _read(rel):
    p = office.ROOT / rel if rel else None
    return p.read_text(encoding="utf-8", errors="replace")[:30000] if p and p.exists() else "(không có kết quả)"


def _history_text(t):
    rows = [f"- Lần {h['round']}: {h['who']} {'DUYỆT' if h['ok'] else 'CHƯA ĐẠT'}: {h['note']}" for h in t.get("history", [])]
    return "\n".join(rows) or "(chưa có)"


# ---------- bắt đầu ----------

FLOWS = ("auto", "fast", "standard", "full")

# ---- mức việc tự chọn: việc cơ bản 1 người làm, việc sâu mới chia nhiều người + duyệt nhiều cấp ----
DEEP_WORDS = (r"toàn bộ|toàn diện|chi tiết|kỹ lưỡng|chuyên sâu|làm sâu|nghiệm thu|kiến trúc|thiết kế hệ thống|nhiều phần|"
              r"phối hợp|cả phòng|end.to.end|refactor|viết paper|bản thảo|thí nghiệm|benchmark|pentest|audit|rà soát toàn")
SIMPLE_WORDS = (r"^(xem|liệt kê|tóm tắt|cho biết|kiểm tra nhanh|đọc|hỏi|tra|tìm|đếm|báo)\b|là gì|bao nhiêu|nhanh|ngắn gọn|"
                r"một câu|1 câu|có không|ở đâu")
PHASE_LEVEL = {"idea": "fast", "lit": "fast", "review": "standard", "code": "standard", "deploy": "standard",
               "security": "standard", "ctf": "standard", "skill": "fast", "results": "standard",
               "writing": "full", "experiment": "full", "design": "full"}
LEVEL_TEXT = {"fast": "⚡ việc cơ bản: 1 người làm, xong trình sếp",
              "standard": "🔎 việc vừa: 1 người làm, trưởng phòng duyệt",
              "full": "🏛️ việc sâu: trưởng phòng chia người, duyệt 2 cấp"}


def classify(text, phase):
    """Đoán mức việc (không tốn lượt gọi model): trả về fast | standard | full."""
    low = text.lower()
    level = PHASE_LEVEL.get(phase, "standard")
    if re.search(DEEP_WORDS, low) or len(text) > 700:
        return "full"
    if re.search(SIMPLE_WORDS, low.strip()) and len(text) < 300:
        return "fast"
    return level


RUN_BUDGET = 8  # một việc chạy quá số lượt AI này (làm + duyệt + hỏi) thì dừng hỏi sếp, tránh quay vòng
PERM_Q = r"quyền|chỉ đọc|read.only|ghi file|tạo file|sửa file|chạy lệnh|không được ghi|write"
CMD_Q = r"lệnh|chạy|python|bash|pdflatex|latexmk|tectonic|docker|gen\.py|solve"  # ⚡ làm → sếp · 🔎 làm → TP duyệt → sếp · 🏛️ làm → TP → Phó sếp → sếp


def over_budget(task_id, who):
    """Việc đã chạy quá ngân sách lượt AI: dừng lại hỏi sếp một lần (sếp trả lời thì có thêm 4 lượt)."""
    t = office.get_task(task_id)
    need_boss(task_id, who, f"Việc đã chạy {t.get('runs', 0)} lượt AI mà chưa xong, có thể đang quay vòng. "
                            "Sếp ghi chỉ đạo rõ hơn để làm tiếp (thêm 4 lượt), hoặc bấm Không đồng ý để dừng.")


def start(dept_id, text, mode, title, flow="full"):
    """Sếp ra lệnh cho phòng: trưởng phòng nhận để chia việc."""
    d, s = _dept(dept_id), office.load()
    head, why_sub = head_of(dept_id)
    staff = [f"@{a['name']} ({a['title']}){'' if usable(k) else ' [ĐANG VẮNG, KHÔNG GIAO]'}: {a.get('role', '')[:200]}"
             for k, a in s["agents"].items() if a["dept"] == dept_id and not a.get("system")]
    t = office.add_task(title, head, office.guess_phase(text), actor="boss")
    office.set_task_fields(t["id"], stage="assign", dept=dept_id, request=text, mode=mode, children=[], flow=flow)
    body = (f"Sếp giao cho {d['name']}:\n{text}\n\nNhân viên trong phòng:\n" + "\n".join(staff))
    office.send_mail("boss", head, "assign", f"Phân việc: {title}", body, task_id=t["id"], stage="assign",
                     reason="sếp giao việc cho phòng, trưởng phòng chia")
    office.log(office.DEPUTY, f"Chuyển lệnh của sếp cho {'quyền ' if why_sub else ''}trưởng phòng {_name(head)}: {title}"
               + (f" ({why_sub})" if why_sub else ""), kind="task")
    return {**office.get_task(t["id"]), "why": f"trưởng phòng {_name(head)} chia việc", "mail": True}


def start_direct(dept_id, owner, text, mode, title, parent=None, frm="boss", flow=None):
    """Giao thẳng cho một người (sếp chỉ định @người, hoặc trưởng phòng chia xuống); vẫn qua các bước duyệt."""
    owner, why_sub = acting(dept_id, owner)
    if why_sub:
        office.log(office.DEPUTY, why_sub, kind="task")
    t = office.add_task(title, owner, office.guess_phase(text), actor="boss")
    if flow is None:  # việc con theo mức quy trình của lệnh gốc
        flow = (office.get_task(parent) or {}).get("flow", "full") if parent else "full"
    office.set_task_fields(t["id"], stage="work", dept=dept_id, request=text, mode=mode, rounds=0, history=[],
                           parent=parent, flow=flow)
    _send_work(t["id"], text, frm=frm, reason="lần đầu: " + ("sếp giao" if frm == "boss" else f"{_name(frm)} chia việc"))
    return {**office.get_task(t["id"]), "why": "giao thẳng, vẫn qua trưởng phòng và Phó sếp duyệt", "mail": True}


def _send_work(task_id, body, frm="boss", reason=""):
    t = office.get_task(task_id)
    kind = office.PHASE_KIND.get(t["phase"], "task")
    office.send_mail(frm, t["owner"], kind, t["title"], body, mode=t.get("mode", "read"), task_id=t["id"], stage="work",
                     reason=reason)
    office.move_task(t["id"], "todo", actor=frm)


# ---------- sau mỗi bước ----------

def after(agent_id, meta, text, out_rel):
    """workers.py gọi sau khi nhân viên làm xong một thư có `stage:`."""
    t = office.get_task(meta.get("task"))
    if not t:
        return
    stage = meta.get("stage")
    if stage == "assign":
        _after_assign(t, agent_id, text)
    elif stage == "work":
        _after_work(t, agent_id, out_rel)
    elif stage in ("lead_review", "deputy_review"):
        _after_review(t, agent_id, stage, text)


def _after_assign(t, head, text):
    s = office.load()
    dept_id = t["dept"]
    by_name = {a["name"].lower(): k for k, a in s["agents"].items() if a["dept"] == dept_id and not a.get("system")}
    by_name.update({k: k for k in by_name.values()})
    children = []
    for who, desc in ASSIGN.findall(text):
        owner = by_name.get(who.lower())
        if not owner:
            continue
        c = start_direct(dept_id, owner, f"{desc.strip()}\n\nYêu cầu gốc của sếp:\n{t['request']}", t.get("mode", "read"),
                         desc.strip()[:140], parent=t["id"], frm=head)
        children.append(c["id"])
        office.log(head, f"Giao #{c['id']} cho {_name(owner)}: {desc.strip()[:70]}", kind="mail", to=owner)
    if not children:  # trưởng phòng không chia: tự làm, rồi lên Phó sếp duyệt
        office.set_task_fields(t["id"], stage="work", rounds=0, history=[])
        _send_work(t["id"], t["request"], frm="boss", reason=f"trưởng phòng {_name(head)} không chia, tự làm")
        office.log(head, f"Tự nhận làm: {t['title']}", kind="task")
        return
    office.set_task_fields(t["id"], stage="assigned", children=children)
    office.move_task(t["id"], "doing", actor=head)


PKG = re.compile(r"challenges[\\/]+nhap[\\/]+([\w.-]+)", re.I)


def _blind_test(task_id, worker, out_rel):
    """Người tạo đề KHÔNG tự giải/thử: nộp gói xong, văn phòng giao Mò giải mù (tools/tester.py, không biết gì về đề).
    ĐẠT → trưởng phòng duyệt như thường. TRƯỢT → trả lại người tạo đề kèm cách Mò đã giải. Lỗi → hỏi sếp."""
    t = office.get_task(task_id)
    root = Path("E:/CTF/challenges/nhap")
    try:
        import tester
        root = tester.CHALL_ROOT / "nhap"
    except Exception:  # noqa: BLE001
        pass
    pkgs = sorted({m for m in PKG.findall(_read(out_rel)) if (root / m).is_dir()})
    if not pkgs:
        return rework(task_id, "Văn phòng", "Báo cáo không ghi gói đề nào trong challenges/nhap/<gói> (hoặc gói không có). "
                                          "Ghi rõ đường dẫn gói đã tạo để Mò thử mù.")
    notes, verdict = [], "dat"
    for g in pkgs:
        office.log("mo",f"🧪 Thử mù gói {g} do {_name(worker)} nộp", kind="task")
        code, out = office.tester_run_wait(root / g)
        lines = [ln for ln in out.splitlines() if ln.strip()][-12:]
        notes.append(f"Gói {g}:\n" + "\n".join(lines))
        if "Không thấy challenges.json" in out:
            return rework(task_id, "Mò (thử mù)", f"Gói {g} thiếu challenges.json (hoặc challenge.json) nên Mò không thử được. "
                                                  "Hoàn thiện gói theo skill dang-de-len-portal rồi nộp lại.")
        if "❌ TRƯỢT" in out:
            verdict = "truot"
        elif verdict == "dat" and (code or "⛔" in out or "⚠️ LỖI" in out):
            verdict = "loi"
    note = "\n\n".join(notes)[:1500]
    t = office.get_task(task_id)
    hist = t.get("history", []) + [{"round": t.get("rounds", 0) + 1, "who": "Mò (thử mù)", "stage": "blind_test",
                                    "ok": verdict == "dat", "note": note, "t": office.now()}]
    office.set_task_fields(task_id, history=hist)
    if verdict == "truot":
        return rework(task_id, "Mò (thử mù)", "AI giải được đề trong 2 phút. Làm khó với AI hơn (không làm mập mờ với người), "
                                              "KHÔNG tự thử lại; nộp lại thì Mò thử tiếp.\n" + note)
    if verdict == "loi":
        return need_boss(task_id, "mo", "Bài thử mù không chạy được hoặc bị chặn (đã trượt nhiều lần):\n" + note +
                         "\nPhương án: ghi chỉ đạo cho người tạo đề sửa gói; hoặc Không đồng ý = dừng.")
    _after_work(office.get_task(task_id), worker, out_rel, tested=True)


def _chain_check(dept):
    """Máy kiểm tra của phòng (vd. tools/check_assets.py): (đạt?, đuôi kết quả). Không tốn lượt AI."""
    import subprocess
    import sys as _sys
    cmd = dept.get("chain_check")
    if not cmd:
        return True, "(phòng không có máy kiểm tra)"
    py = Path(_sys.executable)
    py = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists() else py
    try:
        r = subprocess.run([str(py), *cmd], cwd=dept.get("workdir") or None, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
        return r.returncode == 0, tail
    except Exception as e:  # noqa: BLE001
        return False, f"máy kiểm tra lỗi: {e}"


def _chain_after(t, worker, out_rel):
    """Chuỗi tự động (sếp vắng, sếp giao quyền tự quyết): máy kiểm tra đạt → tự duyệt, giao bước sau.
    Chưa đạt → trả lại người làm (tối đa MAX_ROUNDS lần); vẫn chưa đạt → để chờ sếp và đi tiếp bước sau."""
    dept_id = t.get("dept", "")
    ok, tail = _chain_check(_dept(dept_id))
    hist = t.get("history", []) + [{"round": t.get("rounds", 0) + 1, "who": "Máy kiểm tra", "stage": "chain_check",
                                    "ok": ok, "note": tail[-1500:], "t": office.now()}]
    office.set_task_fields(t["id"], history=hist)
    if ok:
        office.set_task_fields(t["id"], stage="done", auto_signed=True)
        office.move_task(t["id"], "done", actor="boss")
        office.log(office.DEPUTY, f"🤖 Tự duyệt bước #{t['id']} (máy kiểm tra đạt, sếp vắng): {t['title'][:70]}", kind="review")
        return chain_done(dept_id, t["id"])
    if t.get("rounds", 0) < MAX_ROUNDS:
        return rework(t["id"], "Máy kiểm tra", "tools/check_assets.py còn lỗi, sửa cho 0 lỗi:\n" + tail)
    _to_boss(t["id"], "Chuỗi tự động: máy kiểm tra vẫn lỗi sau 2 lần sửa, để sếp xem khi về:\n" + tail)
    office.log(office.DEPUTY, f"⏭️ Bước #{t['id']} chưa đạt máy kiểm tra, để chờ sếp; chuỗi đi tiếp", kind="review")
    return chain_done(dept_id, t["id"])


def chain_done(dept_id, task_id):
    """Một việc của bước hiện tại xong (đạt / để chờ sếp). Bước là NHÓM song song thì chờ đủ cả nhóm mới đi tiếp.
    Mỗi việc chỉ đếm MỘT lần (lỗi thật 2026-10-28: Bánh hỏi sếp 2 lần bị trừ 2 → V2-6, V2-7 giao khi nhóm chưa xong)."""
    with office._lock:
        s = office.load()
        d = s["depts"].get(dept_id, {})
        seen = d.setdefault("chain_done_ids", [])
        if task_id in seen:
            return None
        seen.append(task_id)
        left = max(int(d.get("chain_wait", 0)) - 1, 0)
        d["chain_wait"] = left
        office.save(s)
    if left > 0:
        office.log(office.DEPUTY, f"⏳ {d.get('name', dept_id)}: còn {left} việc song song chưa xong", kind="task")
        return None
    return chain_next(dept_id)


def chain_next(dept_id):
    """Giao bước kế tiếp trong dept.chain: {owner, title, text} (1 việc) hoặc {group: [...]} (nhiều người làm SONG SONG,
    đủ cả nhóm xong mới sang bước sau). Quy trình mỗi việc: làm → máy tự kiểm."""
    with office._lock:
        s = office.load()
        d = s["depts"].get(dept_id, {})
        pos = int(d.get("chain_pos", 0))
        steps = d.get("chain") or []
        if pos >= len(steps):
            d["chain"] = None
            office.save(s)
            office.log(office.DEPUTY, f"🏁 {d.get('name', dept_id)}: xong cả chuỗi tự động, chờ sếp về xem", kind="task")
            return None
        group = steps[pos].get("group") or [steps[pos]]
        d["chain_pos"], d["chain_wait"], d["chain_done_ids"] = pos + 1, len(group), []
        office.save(s)
    out = None
    for st in group:
        r = start_direct(dept_id, st["owner"], st["text"], "write", st["title"], flow="fast")
        office.set_task_fields(r["id"], chain_step=pos, granted_write=True, deliver="file")
        office.log(office.DEPUTY, f"🤖 Chuỗi tự động bước {pos + 1}/{len(steps)}"
                   + (f" (song song {len(group)} người)" if len(group) > 1 else "")
                   + f" → {_name(st['owner'])}: {st['title']}", kind="task", to=st["owner"])
        out = out or r
    return out


def _after_work(t, worker, out_rel, tested=False):
    office.set_task_fields(t["id"], output=out_rel)
    if not tested and office.load()["agents"].get(worker, {}).get("maker"):  # người tạo đề nộp → Mò thử mù trước
        import threading
        office.set_task_fields(t["id"], stage="blind_test")
        office.move_task(t["id"], "review", actor=worker)
        threading.Thread(target=_blind_test, args=(t["id"], worker, out_rel), daemon=True).start()
        return
    if t.get("chain_step") is not None and _dept(t.get("dept", "")).get("chain"):  # chuỗi tự động khi sếp vắng
        return _chain_after(t, worker, out_rel)
    if t.get("flow") == "fast":  # ⚡ nhanh: làm xong trình sếp luôn
        return _to_boss(t["id"], "Quy trình nhanh: chưa qua duyệt.")
    head, _ = acting(t.get("dept", ""), _dept(t.get("dept", "")).get("head"), exclude=(worker,))
    if head and head != worker and usable(head):
        _ask_review(t["id"], head, "lead_review")
    else:  # trưởng phòng tự làm (hoặc không có trưởng phòng) thì lên thẳng Phó sếp
        _to_deputy(t["id"])


LIGHT_PHASES = {"lit", "idea"}  # việc nhẹ: TP duyệt đạt thì trình thẳng sếp, khỏi qua Phó sếp
HEAVY_PHASES = {"writing", "code", "deploy", "security", "experiment", "results", "design", "ctf"}  # Phó sếp dùng model mạnh
SUMMARY_OVER = 8000  # kết quả dài hơn (ký tự) thì Phó sếp đọc tóm tắt + dàn ý, cần thì tự mở file


def digest(text, path):
    """Bản rút gọn cho Phó sếp: mục Tóm tắt + dàn ý các đề mục + đường dẫn bản đầy đủ (không tốn lượt gọi model)."""
    m = re.search(r"^#+\s*Tóm tắt.*?$(.*?)(?=^#+\s|\Z)", text, re.M | re.S | re.I)
    summary = (m.group(1).strip() if m else text[:2500].strip())[:3000]
    outline = "\n".join(ln for ln in text.splitlines() if ln.lstrip().startswith("#"))[:2000]
    return (f"(Kết quả dài {len(text)} ký tự: dưới đây là TÓM TẮT và DÀN Ý. Bản đầy đủ: {office.ROOT / path}. "
            f"Chỉ mở file bằng công cụ đọc file khi cần kiểm chứng một điểm nghi ngờ.)\n\n"
            f"### Tóm tắt\n{summary}\n\n### Dàn ý\n{outline or '(không có đề mục)'}")


def _ask_review(task_id, reviewer, stage, reason=""):
    t = office.get_task(task_id)
    who = "TRƯỞNG PHÒNG duyệt lần 1" if stage == "lead_review" else "PHÓ SẾP duyệt lần 2"
    full = _read(t.get("output"))
    shown = digest(full, t.get("output", "")) if stage == "deputy_review" and len(full) > SUMMARY_OVER else full
    body = (f"{who} cho việc #{t['id']} của {_name(t['owner'])}.\n\n## Yêu cầu\n{t.get('request', t['title'])}\n\n"
            f"## Các lần duyệt trước\n{_history_text(t)}\n\n## Kết quả cần duyệt ({t.get('output', '')})\n{shown}")
    office.set_task_fields(task_id, stage=stage)
    office.move_task(task_id, "review", actor=t["owner"])
    office.send_mail(t["owner"], reviewer, "approve", f"Duyệt #{t['id']}: {t['title'][:80]}", body,
                     task_id=t["id"], stage=stage,
                     reason=reason or ("trưởng phòng duyệt lần 1" if stage == "lead_review" else "Phó sếp duyệt lần 2")
                     + (f" (bài nộp lại sau {t.get('rounds')} lần trả)" if t.get("rounds") else ""))


def _to_deputy(task_id):
    dep = office.load()["agents"].get(office.DEPUTY, {})
    if dep.get("auto"):
        _ask_review(task_id, office.DEPUTY, "deputy_review")
    else:  # Phó sếp chưa có model để duyệt: trình thẳng sếp
        _to_boss(task_id, "Phó sếp chưa được giao model để duyệt nên trình thẳng sếp.")


def _after_review(t, reviewer, stage, text):
    m = None
    for m in VERDICT.finditer(text):  # lấy kết luận cuối cùng
        pass
    if m is not None and m.group(1) == "CẦN SẾP":
        return need_boss(t["id"], reviewer, m.group(2).strip())
    ok = (m is None) or m.group(1) == "DUYỆT"
    note = (m.group(2).strip() if m else "(người duyệt không ghi kết luận rõ, coi như đạt)")[:1500]
    hist = t.get("history", []) + [{"round": t.get("rounds", 0) + 1, "who": _name(reviewer), "stage": stage,
                                    "ok": ok, "note": note, "t": office.now()}]
    office.set_task_fields(t["id"], history=hist)
    office.log(reviewer, f"{'✅ Duyệt' if ok else '↩️ Trả lại'} #{t['id']}: {note[:90]}", kind="review")
    if not ok:
        return rework(t["id"], _name(reviewer), note)
    if stage == "lead_review":
        if t.get("flow") == "standard":  # 🔎 chuẩn: trưởng phòng duyệt xong trình sếp, bỏ Phó sếp
            return _to_boss(t["id"], f"Quy trình chuẩn, trưởng phòng đã duyệt: {note}")
        if t.get("phase") in LIGHT_PHASES:
            office.log(office.DEPUTY, f"#{t['id']} là việc nhẹ, trưởng phòng đã duyệt đạt: trình thẳng sếp, Phó sếp không duyệt lại")
            _to_boss(t["id"], f"Việc nhẹ ({t.get('phase')}), trưởng phòng đã duyệt: {note}")
        else:
            _to_deputy(t["id"])
    else:
        _to_boss(t["id"], note)


def need_boss(task_id, who, question):
    """Việc dừng lại chờ sếp quyết (không tính là bị trả lại). Sếp trả lời ở mục Chờ sếp → việc tự chạy tiếp."""
    t = office.get_task(task_id)
    if not t:
        return
    asks = sum(1 for h in t.get("history", []) if h.get("stage") == "boss_answer")
    if asks >= 3:  # đã hỏi sếp 3 lần mà vẫn hỏi tiếp: dừng hẳn, không quay vòng nữa
        office.set_task_fields(task_id, stage="cancelled")
        office.move_task(task_id, "done", actor="boss")
        office.log(who, f"■ Dừng việc #{task_id}: đã hỏi sếp {asks} lần vẫn chưa xong (lần này: {question[:80]}). "
                        "Sếp giao lại với chỉ đạo rõ hơn nếu cần.", kind="ask")
        return
    office.set_task_fields(task_id, stage="waiting_boss")
    office.move_task(task_id, "review", actor=who)
    office.request_approval(who, "ask", f"Cần sếp quyết việc #{task_id}: {t['title'][:70]}", question[:1800], ref=str(task_id))
    office.log(who, f"⏸️ Dừng việc #{task_id} chờ sếp quyết: {question[:90]}", kind="ask")
    # Chuỗi tự động: câu hỏi KHÔNG đẩy chuỗi đi tiếp (bước sau có thể cần kết quả bước này); trả lời xong, việc làm
    # tiếp và chỉ khi xong thật (_chain_after) mới đếm là xong.


def boss_answered(approval, ok, note):
    """Sếp trả lời câu hỏi [CẦN SẾP]: gửi câu trả lời về người làm, việc chạy tiếp (không tính vòng)."""
    t = office.get_task(approval.get("ref"))
    if not t:
        return
    if not ok and not note.strip():  # từ chối không kèm chỉ đạo: dừng việc, tránh vòng hỏi đi hỏi lại
        office.set_task_fields(t["id"], stage="cancelled")
        office.move_task(t["id"], "done", actor="boss")
        office.log("boss", f"■ Sếp không đồng ý, dừng việc #{t['id']}: {t['title'][:80]}", kind="task", to=t.get("owner"))
        return
    answer = note.strip() or ("Sếp đồng ý phương án bạn đề xuất." if ok else "Sếp không đồng ý.")
    q = str(approval.get("detail", "")).lower()
    if ok and t.get("mode") != "write" and re.search(PERM_Q, q):  # đồng ý câu hỏi xin quyền = đổi chế độ chạy thật
        req = re.sub(r"\n*\[Cách nhận kết quả\][^\n]*", "", t.get("request") or t["title"]).rstrip()
        cmds = bool(re.search(CMD_Q, q))
        office.set_task_fields(t["id"], mode="write", granted_write=True, allow_cmds=cmds or bool(t.get("allow_cmds")),
                               request=req + "\n\n[Quyền] Sếp đã cấp quyền ghi file" + (" và chạy lệnh" if cmds else "")
                               + ". Làm luôn, không hỏi lại về quyền.")
        office.log("boss", f"🔓 Đồng ý = cấp quyền ghi{' + chạy lệnh' if cmds else ''} cho việc #{t['id']}", kind="task")
        t = office.get_task(t["id"])
    office.set_task_fields(t["id"], budget=int(t.get("runs", 0)) + 4)  # sếp trả lời: cho thêm 4 lượt
    res = t.get("resume") or {}
    if res.get("stage") in ("lead_review", "deputy_review") and ok:  # lỗi lúc duyệt: chạy lại đúng bước duyệt
        office.set_task_fields(t["id"], resume=None, history=t.get("history", []) + [
            {"round": t.get("rounds", 0), "who": "Sếp", "stage": "boss_answer", "ok": ok, "note": answer, "t": office.now()}])
        return _ask_review(t["id"], res["who"], res["stage"], reason=f"sếp cho duyệt lại sau lỗi: {answer[:80]}")
    office.set_task_fields(t["id"], stage="work",
                           history=t.get("history", []) + [{"round": t.get("rounds", 0), "who": "Sếp", "stage": "boss_answer",
                                                             "ok": ok, "note": answer, "t": office.now()}])
    body = (f"📌 SẾP ĐÃ TRẢ LỜI câu hỏi của việc này:\n{answer}\n\n(Câu hỏi: {approval.get('detail', '')[:800]})\n\n"
            f"## Yêu cầu\n{t.get('request', t['title'])}\n\n## Kết quả lần trước\n{_read(t.get('output'))}")
    why = ("sếp đồng ý cấp quyền ghi" if t.get("granted_write") and re.search(PERM_Q, q) and ok
           else "sếp trả lời câu hỏi [CẦN SẾP]") + f": {answer[:100]}"
    _send_work(t["id"], body, frm="boss", reason=why)


def rework(task_id, who, issues):
    t = office.get_task(task_id)
    rounds = t.get("rounds", 0) + 1
    if rounds > MAX_ROUNDS:  # trả lại quá nhiều: sếp quyết
        office.set_task_fields(task_id, rounds=rounds)
        return _to_boss(task_id, f"Đã trả lại {rounds - 1} lần, vẫn chưa đạt. Vấn đề lần cuối ({who}): {issues}")
    office.set_task_fields(task_id, stage="work", rounds=rounds)
    body = (f"↩️ Việc bị {who} TRẢ LẠI (lần {rounds}). Sửa cho đạt rồi nộp lại.\n\n## Vấn đề cần sửa\n{issues}\n\n"
            f"## Yêu cầu\n{t.get('request', t['title'])}\n\n## Kết quả lần trước\n{_read(t.get('output'))}")
    _send_work(task_id, body, frm=office.DEPUTY, reason=f"bị {who} trả lại (lần {rounds}): {issues[:120]}")


def _to_boss(task_id, note):
    t = office.get_task(task_id)
    office.set_task_fields(task_id, stage="boss_sign")
    office.move_task(task_id, "review", actor=office.DEPUTY)
    detail = (f"Việc: {t.get('request', t['title'])[:600]}\nNgười làm: {_name(t['owner'])}\nKết quả: {t.get('output', '')}\n\n"
              f"Các lần duyệt:\n{_history_text(t)}\n\nGhi chú: {note}")
    aid = office.request_approval(t["owner"], "sign", f"Ký duyệt #{t['id']}: {t['title'][:80]}", detail, ref=str(t["id"]))
    office.set_task_fields(task_id, sign=aid)


def boss_signed(approval, ok, note):
    t = office.get_task(approval.get("ref"))
    if not t:
        return
    if ok:
        office.set_task_fields(t["id"], stage="done")
        office.move_task(t["id"], "done", actor="boss")
        _close_parent(t.get("parent"))
    else:
        rework(t["id"], "Sếp", note or "Sếp chưa duyệt, xem lại toàn bộ.")


def _close_parent(pid):
    if not pid:
        return
    p = office.get_task(pid)
    kids = [office.get_task(c) for c in (p or {}).get("children", [])]
    if p and kids and all(k and k.get("stage") == "done" for k in kids):
        office.set_task_fields(pid, stage="done")
        office.move_task(pid, "done", actor="boss")


def output_path(agent_id, mail_stem):
    return Path("outputs") / agent_id / f"{mail_stem}.md"
