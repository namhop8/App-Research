"""Nhân viên tự nhận thư trong inbox/ và làm việc bằng nhà cung cấp AI của mình.

    python workers.py once     # xử lý hết thư đang chờ rồi thoát
    python workers.py watch    # kiểm tra hộp thư liên tục (office.py serve tự bật cái này)

Thư gửi nhân viên X có tên dạng *_to_X_*.md. Kết quả ghi vào `output:` của thư
(mặc định outputs/<X>/<tên thư>.md), rồi thư được đổi đuôi thành .done.md.
Mặc định chạy chỉ đọc. Thư có `mode: write` phải được sếp duyệt qua Thư ký trước,
khi đó nhân viên được sửa file trong `workdir:` (lệnh nguy hiểm vẫn bị hook hỏi lại).
"""
import pathlib
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import office  # noqa: E402
import providers  # noqa: E402
import workflow  # noqa: E402

ROOT = office.ROOT
TEXT_EXT = {".md", ".tex", ".txt", ".bib", ".py", ".json", ".csv", ".yaml", ".yml", ".log", ".html", ".js", ".css"}
INLINE_LIMIT = 400_000  # ký tự

KIND_PROMPT = {
    "review": (
        "Bạn là Reviewer 2 khó tính của một tạp chí Q1 / hội nghị CORE A*. Review bản thảo được gửi kèm. "
        "Tìm: rò rỉ dữ liệu (leakage), baseline không công bằng, metric thiên lệch, claim vượt quá bằng chứng, "
        "thiếu ablation, trích dẫn không đạt chuẩn Q1/A*, chỗ mâu thuẫn số liệu. "
        "Trả lời bằng tiếng Việt, dạng Markdown: Tóm tắt, Điểm mạnh, Điểm yếu nghiêm trọng (đánh số, kèm vị trí), "
        "Điểm yếu nhỏ, Câu hỏi cho tác giả, Khuyến nghị (accept/minor/major/reject)."
    ),
    "lit": (
        "Bạn là Thủ thư nghiên cứu. Tổng hợp tài liệu theo yêu cầu. Chỉ đưa bài Q1 / CORE A*, "
        "mỗi bài kèm DOI hoặc arXiv ID. Nếu không chắc một trích dẫn có thật thì ghi rõ [CHƯA XÁC MINH]. "
        "Trả lời bằng tiếng Việt, dạng Markdown, kết thúc bằng mục 'Research gap'."
    ),
    "code": (
        "Bạn là kỹ sư phần mềm. Làm việc được giao trong thư mục làm việc. Nếu chỉ có quyền đọc: trả về kế hoạch "
        "và patch dạng unified diff. Nếu có quyền ghi: sửa code, chạy test, rồi báo cáo đã sửa gì và kết quả test. "
        "Không deploy, push hay ssh trừ khi thư yêu cầu rõ. Trả lời bằng tiếng Việt, dạng Markdown."
    ),
    "task": "Làm việc được giao trong thư dưới đây. Trả lời bằng tiếng Việt, dạng Markdown.",
    "assign": workflow.ASSIGN_PROMPT,
    "approve": workflow.APPROVE_PROMPT,
}

_busy = set()
_running = {}  # agent_id → (task_id, tiến trình CLI) đang chạy; để dừng khi việc bị đóng


def cancel_task(task_id):
    """Việc bị đóng (sếp ký / dừng): dừng ngay lượt đang chạy của việc đó."""
    for aid, (tid, proc) in list(_running.items()):
        if str(tid) == str(task_id):
            office._kill_tree(proc)  # cả cây tiến trình: claude + bash/python con (và Mò nếu đang thử đề)
            office.log(aid, f"Dừng lượt đang chạy vì việc #{task_id} đã đóng")
_backoff = {}
RETRY_AFTER = 120  # lỗi mạng thoáng qua: 2 phút sau thử lại ĐÚNG 1 lần, còn lỗi nữa thì hỏi sếp

# Phân loại lỗi: chỉ lỗi mạng/máy chủ tạm thời mới tự thử lại (1 lần). Lỗi khác chạy lại y hệt cũng hỏng y hệt,
# nên dừng và hỏi sếp 1 lần kèm phương án (BAI_HOC #22).
ERROR_CLASSES = [
    ("login", "chưa đăng nhập / chưa cài", r"đăng nhập|chưa cài|api key|unauthor|not logged|login|401|403 forbidden",
     "Sếp đăng nhập lại (🔑 trong hồ sơ nhân viên) rồi trả lời 'đồng ý' để làm tiếp, hoặc giao người khác"),
    ("perm", "bị chặn quyền", r"auto-denied|permission|denied|không có quyền|not allowed|access is denied|chỉ đọc|read.only",
     "Đồng ý = cấp quyền ghi file + chạy lệnh rồi làm tiếp; hoặc ghi chỉ đạo làm cách khác không cần quyền; "
     "Không đồng ý = dừng việc"),
    ("net", "lỗi mạng / máy chủ tạm thời", r"không kết nối được|connection|econn|network|getaddrinfo|ssl|http 5\d\d|"
     r"\b50[0234]\b|overloaded|529|temporarily|unavailable|try again later",
     "Đồng ý = thử lại lần nữa; Không đồng ý = dừng việc"),
    ("timeout", "chạy quá giờ", r"hết giờ|timed out|timeout",
     "Ghi chỉ đạo thu hẹp việc (làm phần nào trước) để làm tiếp; hoặc Không đồng ý = dừng việc"),
]


def classify_error(msg):
    low = str(msg).lower()
    for key, label, pat, options in ERROR_CLASSES:
        if re.search(pat, low):
            return key, label, options
    return "other", "lỗi chưa rõ", "Ghi chỉ đạo để làm tiếp (vd. đổi người làm / đổi cách làm), hoặc Không đồng ý = dừng việc"


AUTO_NOTE = ("# Bạn đang chạy TỰ ĐỘNG trong văn phòng\n"
             "- Văn phòng tự chấm công và tự chuyển việc cho bạn: KHÔNG chạy office.py, KHÔNG tự cập nhật trạng thái.\n"
             "- Mọi nội dung cần thiết đã nằm trong lời dặn này. Ở chế độ chỉ đọc: KHÔNG chạy lệnh terminal; "
             "cần xem file thì dùng công cụ đọc file. Trả lời thẳng bằng văn bản.\n"
             "- Báo cáo nào cũng MỞ ĐẦU bằng mục `## Tóm tắt` (tối đa 5 dòng: làm gì, kết quả chính, còn vướng gì).\n"
             "- Bị chặn bởi thứ chỉ sếp quyết được (thiếu quyền chạy lệnh / ghi file, thiếu dữ liệu, tiêu chí không làm nổi): "
             "làm hết phần làm được, rồi thêm ở CUỐI một dòng `[CẦN SẾP] <câu hỏi ngắn + các phương án>`. "
             "KHÔNG tự viết thư xin phép vào thư mục nào; dòng [CẦN SẾP] là đủ, văn phòng sẽ chuyển sếp.")


def _rules_for_auto():
    """RULES.md bỏ mục 'Chấm công' (dành cho nhân viên tự báo cáo, không phải nhân viên tự động)."""
    text = (ROOT / "RULES.md").read_text(encoding="utf-8")
    return re.sub(r"## Chấm công.*?(?=\n## )", "", text, flags=re.S)


def _phase_of(meta, body):
    """Loại việc của thư: theo thẻ việc nếu có, không thì đoán từ tiêu đề + nội dung."""
    t = office.get_task(meta["task"]) if meta.get("task") else None
    if t and t.get("phase"):
        return t["phase"]
    return {"lit": "lit", "review": "review", "code": "code"}.get(meta.get("kind"), "") or \
        office.guess_phase(f"{meta.get('subject', '')}\n{body}")


def build_content(meta, body, dept, agent=None):
    stable, variable = build_parts(meta, body, dept, agent)
    return f"{stable}\n\n{variable}"


def build_parts(meta, body, dept, agent=None):
    """(phần cố định, phần thay đổi). Phần cố định giống hệt nhau giữa các lần gọi của cùng nhân viên + loại việc,
    nên được nhà cung cấp lưu cache (đọc lại ~1/10 giá); phần thay đổi (thư, tài liệu) để cuối."""
    rules = _rules_for_auto()
    parts = [AUTO_NOTE, f"# Quy tắc văn phòng\n{rules}"]
    charter = office.charter_text()
    if charter:  # sổ nội quy của sếp: bắt buộc với mọi nhân viên
        parts.insert(0, f"# NỘI QUY CỦA SẾP (bắt buộc tuân thủ)\n{charter}")
    if agent:  # cùng model nhưng mỗi nhân viên làm theo vai riêng
        parts.append(f"# Bạn là {agent.get('name', '')} ({agent.get('title', '')})\n{agent.get('role', '')}".strip())
    # Kỹ năng của phòng: đưa nguyên văn để nhân viên làm theo
    have = {k["id"]: k for k in office.list_skills()}
    phase = _phase_of(meta, body)
    for sid in (dept or {}).get("skills", []):
        # chỉ đưa kỹ năng hợp loại việc (vd. humanizer khi viết/review), đỡ tốn token
        if sid in have and (not have[sid]["phases"] or phase in have[sid]["phases"]):
            body_ = pathlib.Path(have[sid]["path"]).read_text(encoding="utf-8", errors="replace")[:20000]
            parts.append(f"# Kỹ năng của phòng: {have[sid]['name']}\n{body_}")
    if dept and dept.get("id") != office.SKILL_DEPT:
        parts.append("# Thiếu kỹ năng?\nNếu việc này cần một kỹ năng/quy trình chuyên môn mà phòng chưa có, "
                     "làm hết sức có thể rồi thêm vào CUỐI báo cáo một dòng riêng: "
                     "[CẦN KỸ NĂNG] <mô tả ngắn kỹ năng cần có>. Phòng Kỹ năng sẽ làm giúp.")
    if dept:
        parts.append(f"# Quy định của {dept.get('name', '')}\n{dept.get('notes', '')}")
    if dept and dept.get("dirs"):
        parts.append("# Thư mục phòng được phép đọc\n" + "\n".join(f"- {d}" for d in dept["dirs"]))
    stable, parts = "\n\n".join(parts), []
    mode = meta.get("mode", "read")
    workdir = meta.get("workdir") or ""
    cmds = mode == "write" and bool((dept or {}).get("allow_commands") or (agent or {}).get("perm_cmds"))
    # Nói RÕ được chạy lệnh: Sonnet đọc câu "Ở chế độ chỉ đọc: KHÔNG chạy lệnh" trong AUTO_NOTE rồi tưởng mình chỉ đọc,
    # không dám chạy python, dừng hỏi sếp (lỗi thật 2026-10-28: Kem, Su, Bánh)
    parts.append(f"# Quyền LƯỢT NÀY: {'ĐƯỢC SỬA FILE' if mode == 'write' else 'chỉ đọc'}"
                 + (" VÀ ĐƯỢC CHẠY LỆNH (gõ `python …` trơn, không cần hỏi; KHÔNG phải chế độ chỉ đọc)" if cmds else "")
                 + (f", thư mục làm việc: {workdir}" if workdir else ""))
    parts.append(f"# Thư từ {meta.get('from', '?')}: {meta.get('subject', '')}\n{body}")
    for p in meta.get("inputs", []) or []:
        path = Path(p)
        if path.suffix.lower() in TEXT_EXT and path.exists() and path.stat().st_size < INLINE_LIMIT * 4:
            text = path.read_text(encoding="utf-8", errors="replace")[:INLINE_LIMIT]
            parts.append(f"# Nội dung file {path}\n```\n{text}\n```")
        else:
            parts.append(f"# File cần đọc (dùng công cụ đọc file nếu có): {path}")
    return stable, "\n\n".join(parts)


LIGHT_MODEL = {"antigravity-cli": "gemini-3.8-flash-medium", "claude-cli": "sonnet", "gemini-cli": "gemini-2.5-flash"}


DEPUTY_LIGHT = {"antigravity-cli": "gemini-3.8-flash-high", "claude-cli": "sonnet"}


def _model_for(agent, kind, phase=""):
    """Trưởng phòng duyệt lần 1 bằng model nhẹ. Phó sếp: việc nặng (viết, code, deploy…) giữ model mạnh,
    việc nhỏ dùng model nhẹ cùng tài khoản. Đỡ tốn quota mà cửa cuối vẫn chặt ở chỗ cần chặt."""
    prov = dict(agent["provider"])
    if kind != "approve":
        return prov
    if agent.get("dept") == "reception":  # Phó sếp
        if phase not in workflow.HEAVY_PHASES and prov.get("type") in DEPUTY_LIGHT:
            prov["model"] = DEPUTY_LIGHT[prov["type"]]
    elif prov.get("type") in LIGHT_MODEL:
        prov["model"] = LIGHT_MODEL[prov["type"]]
    return prov


def doing_text(meta, subject, s, task):
    """Câu trạng thái nói rõ đang làm gì (thay vì chỉ chép tiêu đề thư)."""
    stage, kind = meta.get("stage", ""), meta.get("kind", "task")
    owner = s["agents"].get(task.get("owner", ""), {}).get("name", "")
    title = re.sub(r"^(Duyệt|Phân việc) #?\d*:?\s*", "", subject)
    if stage == "assign":
        return f"👑 Chia việc cho phòng: {title}"
    if stage == "lead_review":
        return f"🔎 Duyệt lần 1 bài của {owner}: {title}"
    if stage == "deputy_review":
        return f"🧐 Duyệt lần 2 bài của {owner}: {title}"
    if stage == "work" and task.get("rounds"):
        return f"↩️ Làm lại lần {task['rounds']}: {title}"
    verb = {"lit": "📚 Tìm tài liệu", "review": "🔍 Review", "code": "💻 Code", "approve": "🔎 Duyệt"}.get(kind, "⌨️ Làm")
    return f"{verb}: {title}"


def run_label(task):
    """'· lượt 3 vì: bị Claude trả lại…' khi việc đã chạy hơn 1 lượt (để thấy vì sao lại chạy)."""
    log_ = task.get("run_log") or []
    if len(log_) < 2:
        return ""
    return f" · lượt {log_[-1]['n']} vì: {log_[-1]['reason'][:90]}"


def _close_mail(mail, suffix):
    mail.rename(mail.with_name(mail.name[:-3] + suffix))


def handle(agent_id, mail):
    meta, body = office.parse_mail(mail)
    subject, kind = meta.get("subject", mail.stem), meta.get("kind", "task")
    inputs = meta.get("inputs", []) or []
    mode = meta.get("mode", "read")
    workdir = meta.get("workdir") or ""
    out = ROOT / (meta.get("output") or f"outputs/{agent_id}/{mail.stem}.md")
    title = f"📬 {subject}"
    s = office.load()
    agent = s["agents"][agent_id]
    home = agent.get("work_dept") or agent["dept"]  # ngồi ở phòng khác (vd. Mít cạnh Mò) vẫn làm theo quy định phòng gốc
    dept = {**s["depts"].get(home, {}), "id": home}
    linked = str(meta.get("task", "")).strip()  # thư sinh ra từ một thẻ việc trên bảng
    task = next((t for t in s["tasks"] if linked and str(t["id"]) == linked), None) or \
        next((t for t in s["tasks"] if t["title"] == title and t["owner"] == agent_id and t["column"] != "done"), None)
    if task is None:
        phase = {"lit": "lit", "review": "review", "code": "code"}.get(kind, "idea")
        task = office.add_task(title, owner=agent_id, phase=phase, actor=agent_id)

    if mode == "write" and not (task.get("granted_write") or dept.get("auto_write") or agent.get("perm_write")):  # phòng tự ghi trong thư mục riêng  # sếp đã bấm 🔓 cấp quyền cho việc này thì khỏi xin lại
        office.set_status(agent_id, "waiting", f"Chờ sếp duyệt quyền sửa file: {subject}")
        req = office.request_approval(
            agent_id, "write", f"{agent['name']} xin quyền sửa file trong {workdir or 'ResearchLab'}",
            f"Việc: {subject}\n\n{body[:1200]}", ref=mail.name)
        ok = office.wait_approval(req)
        if not ok:
            _close_mail(mail, ".denied.md")
            if (office.get_task(task["id"]) or {}).get("stage") != "cancelled":  # sếp "dừng hẳn" thì để yên ở Xong
                office.move_task(task["id"], "todo", actor=agent_id)
            office.log(agent_id, f"Không được duyệt nên chưa làm: '{subject}'")
            office.set_status(agent_id, "idle", "")
            return True

    if agent["provider"]["type"] == "gemini-api" and not office.get_secret(agent_id).get("api_key"):
        office.set_status(agent_id, "waiting", "Chờ sếp nhập API key Gemini")
        return False
    started = int(time.time()) - 1
    stage = meta.get("stage", "")
    # Lý do của lượt này: lý do hẹn trước (thử lại sau lỗi / ngủ dậy) > lý do ghi trong thư > lần đầu
    reason = task.get("next_reason") or meta.get("reason") or ("lần đầu" if not task.get("run_log") else "chạy tiếp thư cũ")
    if task.get("next_reason"):
        office.set_task_fields(task["id"], next_reason="")
    office.note_run(task["id"], reason, agent_id, stage)
    task = office.get_task(task["id"]) or task
    if stage and kind != "assign":  # đếm lượt AI của việc; quá ngân sách thì dừng hỏi sếp (chống quay vòng)
        runs = int(task.get("runs", 0)) + 1
        office.set_task_fields(task["id"], runs=runs)
        if runs > int(task.get("budget") or workflow.RUN_BUDGET):
            _close_mail(mail, ".denied.md")
            office.set_status(agent_id, "idle", "")
            workflow.over_budget(task["id"], agent_id)
            return True
    office.clear_steps(agent_id)
    if stage not in ("lead_review", "deputy_review"):  # bước duyệt không kéo thẻ về "đang làm"
        office.move_task(task["id"], "doing", actor=agent_id)
    office.set_status(agent_id, "working", doing_text(meta, subject, s, task) + run_label(task))
    dirs = sorted({str(Path(p).parent) for p in inputs if Path(p).exists()} | ({workdir} if workdir and Path(workdir).exists() else set()))
    cwd = workdir if (mode == "write" and workdir and Path(workdir).exists()) else ROOT
    model = _model_for(agent, kind, _phase_of(meta, body))
    req_text = f"{subject}\n{body}\n{task.get('request', '')}"
    mentioned = {m.rstrip(".,;:)") for m in re.findall(r"[A-Za-z]:\\[^\s'\"<>|*?]*", req_text)}
    mentioned = {str(Path(m)) if Path(m).is_dir() else str(Path(m).parent) for m in mentioned
                 if Path(m).exists() or Path(m).parent.is_dir()}
    explicit = sorted(mentioned)
    dept_dirs = [d for d in dept.get("dirs", []) if Path(d).is_dir()]  # thư mục phòng được phép vào
    # Antigravity không tự cho đọc thư mục đang đứng: luôn cấp thư mục văn phòng + thư mục nhắc tới + thư mục phòng
    dirs = sorted(set(dirs) | mentioned | set(dept_dirs) | {str(ROOT)})
    # Đứng ở thư mục dữ liệu của việc (vd. D:\Paper3) để đường dẫn tương đối như `TRUY_VET_SO_LIEU.md` trỏ đúng chỗ
    data_dir = (explicit or dept_dirs or [None])[0]
    if data_dir:
        cwd = data_dir
    if stage in ("lead_review", "deputy_review"):  # người duyệt được mở bản đầy đủ khi cần kiểm chứng
        dirs = sorted(set(dirs) | {str(ROOT / "outputs")})
    granted_cmds = bool(task.get("allow_cmds") or agent.get("perm_cmds"))  # sếp cấp cho việc / cho người: python / pdflatex…
    maker = bool(agent.get("maker"))  # người tạo đề: chỉ đọc/ghi file, KHÔNG lệnh (giải thử là việc của Mò, thử mù)
    run_args = dict(dirs=dirs, cwd=cwd, write=(mode == "write"),
                    allow_cmds=False if maker else bool(dept.get("allow_commands")) or granted_cmds,
                    allowed_tools=[] if maker else list(dept.get("allowed_tools") or ()) + (office.GRANT_CMDS if granted_cmds else []),
                    web=bool(dept.get("web") or agent.get("perm_web")) and stage not in ("lead_review", "deputy_review"),
                    timeout=600 if kind == "approve" else int(dept.get("timeout") or 1800),  # duyệt tối đa 10 phút
                    on_start=lambda proc: _running.__setitem__(agent_id, (task["id"], proc)))
    instr = KIND_PROMPT.get(kind, KIND_PROMPT["task"])
    office.set_model_now(agent_id, model.get("model") or model["type"])  # kính nhân vật hiện model đang chạy
    try:
        try:
            stable, variable = build_parts(meta, body, dept, agent)
            text = providers.run(model, office.get_secret(agent_id), instr, variable, system=stable, **run_args,
                                 on_step=lambda st: office.set_step(agent_id, st),
                                 on_text=lambda tx, kd: office.set_thought(agent_id, tx, kd),
                                 on_rate=lambda info: office.set_rate(model["type"], info))
        except RuntimeError as e:
            if "auto-denied" not in str(e) and "permission" not in str(e).lower():
                raise
            why = "bị chặn lệnh terminal → chạy lại 1 lần, cấm dùng lệnh"
            office.log(agent_id, f"Lượt mới #{task['id']} vì: {why}")
            office.note_run(task["id"], why, agent_id, stage)
            office.set_status(agent_id, "working", doing_text(meta, subject, s, task) + f" · vì: {why}")
            text = providers.run(model, office.get_secret(agent_id),
                                 instr + "\nTUYỆT ĐỐI KHÔNG dùng lệnh terminal hay công cụ chạy lệnh. Chỉ suy nghĩ và trả lời bằng văn bản.",
                                 variable, system=stable, **run_args)
    except providers.QuotaError as e:
        # Hết token: đi ngủ, thư vẫn nằm trong hộp thư, dậy sẽ làm tiếp
        _running.pop(agent_id, None)
        office.set_model_now(agent_id, "")
        office.record_use(agent_id, ok=False)
        office.move_task(task["id"], "todo", actor=agent_id)
        office.set_task_fields(task["id"], next_reason="ngủ dậy sau khi hết token, làm tiếp thư đang dở")
        office.go_sleep(agent_id, e.retry_after, str(e))
        return False
    except Exception as e:  # noqa: BLE001
        _running.pop(agent_id, None)
        office.set_model_now(agent_id, "")
        if not mail.exists():  # thư đã bị huỷ (sếp cấp quyền / giao lại): lượt cũ bị dừng, không phải lỗi
            office.set_status(agent_id, "idle", "")
            return True
        if (office.get_task(task["id"]) or {}).get("column") == "done":  # bị dừng vì việc đã đóng: không phải lỗi
            _close_mail(mail, ".done.md")
            office.set_status(agent_id, "idle", "")
            return True
        return _on_error(agent_id, mail, task, subject, e)
    office.set_model_now(agent_id, "")
    _running.pop(agent_id, None)
    if not mail.exists():  # thư bị huỷ trong lúc đang làm (sếp cấp quyền / giao lại): bỏ kết quả cũ
        office.set_status(agent_id, "idle", "")
        return True
    if (office.get_task(task["id"]) or {}).get("column") == "done" and stage:  # việc đã đóng trong lúc đang làm: bỏ kết quả
        _close_mail(mail, ".done.md")
        office.set_status(agent_id, "idle", "")
        return True
    office.record_use(agent_id, usage=getattr(text, "usage", None))
    text = str(text)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!-- {agent['name']}, trả lời thư {mail.name} -->\n\n{text}", encoding="utf-8")
    for need in office.NEED_SKILL.findall(text)[:3]:  # nhân viên báo thiếu kỹ năng
        if office.request_skill(agent_id, need.strip(), agent["dept"]):
            office.log(agent_id, f"Nhờ Phòng Kỹ năng: {need.strip()[:80]}", kind="mail")
    if meta.get("for_dept"):  # thợ kỹ năng làm xong: gắn kỹ năng mới cho phòng đã nhờ
        new = [k["id"] for k in office.list_skills() if k["t"] >= started]
        if new:
            office.attach_skills(meta["for_dept"], new)
    _close_mail(mail, ".done.md")
    office.set_conn(agent_id, True, "")
    rel = out.relative_to(ROOT).as_posix()
    need = workflow.NEED_BOSS.search(text) if stage in ("work", "assign") else None
    if need and task:  # người làm bị chặn bởi thứ chỉ sếp quyết được: dừng chờ sếp, không nộp bừa để bị trả lại
        office.log(agent_id, f"Nộp '{subject}' → {rel}", kind="log")
        office.set_task_fields(task["id"], output=rel)
        office.set_status(agent_id, "waiting", "⏸️ Chờ sếp quyết")
        workflow.need_boss(task["id"], agent_id, need.group(1).strip())
        return True
    if stage:  # quy trình cấp bậc: sang bước tiếp theo (duyệt / trả lại / trình sếp ký), chưa ăn mừng
        office.log(agent_id, f"Nộp '{subject}' → {rel}", kind="log")
        office.set_status(agent_id, "idle", "")
        workflow.after(agent_id, meta, text, rel)
        return True
    office.set_task_fields(task["id"], output=rel)  # để nút 👁 Xem / tổng hợp phòng đọc được
    office.move_task(task["id"], "review", actor=agent_id)
    office.log(agent_id, f"Xong '{subject}' → {rel}", kind="done")
    office.set_status(agent_id, "idle", "")
    return True


def _on_error(agent_id, mail, task, subject, e):
    """Lỗi khi chạy: phân loại. Lỗi mạng lần đầu → hẹn thử lại 1 lần (có ghi lý do). Còn lại → đóng thư,
    dừng việc và hỏi sếp ĐÚNG 1 lần kèm phương án (không chạy lại y cũ để hỏng y cũ)."""
    err = str(e)
    key, label, options = classify_error(err)
    if key == "login":
        office.set_conn(agent_id, False, err)
        office.ask_login_if_needed(agent_id, err)
    t = office.get_task(task["id"]) or task
    tries = dict(t.get("err_tries") or {})
    tries[key] = int(tries.get(key, 0)) + 1
    office.set_task_fields(t["id"], err_tries=tries, last_error=f"{label}: {err[:300]}",
                           resume=({"stage": t.get("stage"), "who": agent_id}
                                   if t.get("stage") in ("lead_review", "deputy_review") else None))
    office.log(agent_id, f"Không làm được thư '{subject}' ({label}): {err[:200]}")
    if key == "net" and tries[key] == 1:  # thoáng qua: thử lại đúng 1 lần, lý do hiện trên thẻ việc
        office.set_task_fields(t["id"], next_reason=f"thử lại 1 lần sau {label}: {err[:80]}")
        office.set_status(agent_id, "error", f"{label}, {RETRY_AFTER // 60} phút nữa thử lại 1 lần")
        return False
    _close_mail(mail, ".denied.md")
    if key == "timeout" and t.get("chain_step") is not None and tries[key] <= 3:
        # Chuỗi tự động (sếp vắng): hết giờ không phải hỏng — file đã ghi vẫn còn, làm TIẾP phần dở (tối đa 3 lần)
        office.set_status(agent_id, "idle", "")
        workflow._send_work(t["id"], "⏱️ Lượt trước hết giờ, các file đã ghi VẪN CÒN. Kiểm tra cái đã có, làm TIẾP phần "
                            "còn dở (không làm lại từ đầu), xong chạy tools/check_assets.py rồi báo cáo.\n\n## Yêu cầu\n"
                            + (t.get("request") or t["title"]), frm="boss",
                            reason=f"hết giờ, làm tiếp phần dở (lần {tries[key]}/3)")
        return True
    if not t.get("stage"):  # thư lẻ (không theo quy trình): sếp trả lời xong làm lại rồi trình sếp luôn
        office.set_task_fields(t["id"], flow="fast")
    office.set_status(agent_id, "waiting", f"⏸️ {label}, chờ sếp quyết")
    workflow.need_boss(t["id"], agent_id,
                       f"Lỗi khi chạy ({label}), lần {tries[key]}: {err[:400]}\n"
                       f"Không tự chạy lại vì chạy y cũ sẽ hỏng y cũ. Phương án: {options}.")
    return True


def pending(agent_id):
    return sorted(p for p in office.INBOX.glob(f"*_to_{agent_id}_*.md")
                  if not p.name.endswith((".done.md", ".denied.md")))


def work_queue(agent_id):
    try:
        for mail in pending(agent_id):
            if not handle(agent_id, mail):
                _backoff[agent_id] = time.time()
                return
    except Exception as e:  # noqa: BLE001
        office.log(agent_id, f"Lỗi worker: {e}")
        _backoff[agent_id] = time.time()
    finally:
        _busy.discard(agent_id)


def auto_agents():
    return [k for k, a in office.load()["agents"].items()
            if a.get("auto") and providers.PRESETS.get(a["provider"]["type"], {}).get("kind") in ("cli", "api")]


def retry_now(agent_id):
    _backoff.pop(agent_id, None)


def tick():
    for agent_id in office.wake_due():
        retry_now(agent_id)  # vừa ngủ dậy: làm thư đang dở ngay
    for agent_id in auto_agents():
        if agent_id in _busy or office.sleeping(agent_id) or not pending(agent_id):
            continue
        if time.time() - _backoff.get(agent_id, 0) < RETRY_AFTER:
            continue
        _busy.add(agent_id)
        threading.Thread(target=work_queue, args=(agent_id,), daemon=True).start()


def watch(every=5):  # dò hộp thư mỗi 5 giây
    while True:
        try:
            tick()
        except Exception as e:  # noqa: BLE001
            office.log("boss", f"Lỗi bộ điều phối: {e}")
        time.sleep(every)


def once():
    for agent_id in auto_agents():
        _busy.add(agent_id)
        work_queue(agent_id)


if __name__ == "__main__":
    {"once": once, "watch": watch}.get((sys.argv[1:] or ["once"])[0], once)()
