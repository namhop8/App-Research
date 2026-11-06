"""Phản biện "mù": một nhân viên AI chỉ được đọc đúng một file PDF của bài báo, không biết gì về code, dữ liệu,
nội quy hay ghi chú của văn phòng.

    python tools/blind_review.py <file.pdf> [nhân viên, mặc định gemini] [tên ngắn]

Trích chữ của PDF, chia thành các đoạn và đưa THẲNG vào lời nhắn (model không cần đọc file, không cần chạy lệnh,
thư mục làm việc trống, nằm ngoài dự án). Mỗi đoạn một lượt ghi chú, lượt cuối viết báo cáo từ các ghi chú.
Kết quả lưu outputs/<nhân viên>/ và hiện như một việc 📺 trong app. Thẻ việc đánh dấu external: văn phòng không
giao lại, không đưa vào quy trình duyệt (giao lại theo cách thường sẽ làm mất tính "mù").
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import office  # noqa: E402
import providers  # noqa: E402

# Thư mục làm việc tách riêng của người phản biện mù (không thấy gì khác của văn phòng). Đổi bằng BLIND_REVIEW_DIR.
SANDBOX = Path(os.environ.get("BLIND_REVIEW_DIR") or Path(tempfile.gettempdir()) / "Review-Mu")
CHUNK = 15000  # ký tự mỗi đoạn: vừa lời nhắn đưa thẳng vào dòng lệnh (agy)
ROLE = ("Bạn là reviewer của một tạp chí Q1 về an ninh mạng (Computers & Security / Expert Systems with Applications). "
        "Bạn chỉ có văn bản của MỘT bài báo (chữ trích từ file PDF) được dán trong lời nhắn. Không dùng công cụ, không "
        "đọc file, không chạy lệnh: chỉ trả lời bằng chữ. Viết tiếng Việt.")
NOTE = (ROLE + " Đây là phần {i}/{n} của bài. Ghi chú phản biện cho riêng phần này (tối đa ~450 từ): nội dung chính, "
        "các con số/kết quả quan trọng (ghi đúng số, bảng, hình, trang nếu thấy), điểm yếu, chỗ mâu thuẫn hoặc thiếu.")
FINAL = (ROLE + " Dưới đây là ghi chú của bạn cho từng phần của bài (đọc theo thứ tự). Viết BÁO CÁO PHẢN BIỆN cuối, Markdown:\n"
         "## Tóm tắt (3-5 dòng: bài làm gì, đóng góp chính, kết luận của bạn)\n## Điểm mạnh\n"
         "## Vấn đề lớn (đánh số; mỗi vấn đề chỉ rõ mục/bảng/hình, vì sao là vấn đề, cách sửa cụ thể)\n## Vấn đề nhỏ\n"
         "## Tính nhất quán (số trong chữ so với bảng/hình, định nghĩa, ký hiệu)\n"
         "## Quyết định (Accept / Minor revision / Major revision / Reject, kèm lý do)\n## Venue phù hợp nhất (và vì sao)\n"
         "Khó tính nhưng công bằng, không khen xã giao. Chỉ dựa vào ghi chú, không bịa thêm.")


def pdf_text(pdf):
    try:
        r = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, timeout=120, check=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        text = r.stdout.decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        from pypdf import PdfReader
        text = "\n\n".join(p.extract_text() or "" for p in PdfReader(str(pdf)).pages)
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(ln for i, ln in enumerate(lines) if ln or (i and lines[i - 1]))  # gộp dòng trống thừa


def chunks(text, size=CHUNK):
    out, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) > size and cur:
            out.append(cur)
            cur = ""
        cur += para[: size] + "\n\n"
    return out + ([cur] if cur.strip() else [])


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf = Path(sys.argv[1])
    who = sys.argv[2] if len(sys.argv) > 2 else "gemini"
    tag = sys.argv[3] if len(sys.argv) > 3 else pdf.parent.name.lower()
    agent = office.load()["agents"][who]
    box = SANDBOX / f"{tag}-{int(time.time())}"  # thư mục làm việc TRỐNG, ngoài dự án
    box.mkdir(parents=True)
    parts = chunks(pdf_text(pdf))
    title = f"🙈 Phản biện mù (chỉ PDF): {pdf.name}"
    t = office.add_task(title, who, "review", actor="boss")
    office.set_task_fields(t["id"], deliver="show", mode="read", external=True, request=f"Chỉ đọc chữ của {pdf}")
    office.set_status(who, "working", title)
    office.set_model_now(who, agent["provider"].get("model") or agent["provider"]["type"])
    office.log("boss", f"Giao {agent['name']} phản biện mù, chỉ đọc PDF {pdf.name} ({len(parts)} đoạn)", kind="mail", to=who)
    run = dict(dirs=[str(box)], cwd=str(box), timeout=900, write=False)
    notes, text = [], ""
    try:
        for i, part in enumerate(parts, 1):
            office.set_step(who, f"📖 Đọc phần {i}/{len(parts)} của bài")
            r = providers.run(agent["provider"], office.get_secret(who), NOTE.format(i=i, n=len(parts)), part, **run)
            office.record_use(who, usage=getattr(r, "usage", None))
            notes.append(f"### Phần {i}/{len(parts)}\n{str(r).strip()}")
        office.set_step(who, "✍️ Viết báo cáo phản biện")
        r = providers.run(agent["provider"], office.get_secret(who), FINAL, "\n\n".join(notes)[:19000], **run)
        office.record_use(who, usage=getattr(r, "usage", None))
        text = str(r).strip() + "\n\n---\n<details><summary>Ghi chú từng phần</summary>\n\n" + "\n\n".join(notes) + "\n</details>"
    except Exception as e:  # noqa: BLE001
        text = f"## Tóm tắt\nKhông chạy được: {e}\n\n" + "\n\n".join(notes)
    rel = Path("outputs") / who / f"{datetime.now():%Y-%m-%d_%H%M%S}_phan-bien-mu-{tag}.md"
    (office.ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (office.ROOT / rel).write_text(f"<!-- {agent['name']}, phản biện mù: chỉ đọc chữ của {pdf} -->\n\n{text}", encoding="utf-8")
    office.set_task_fields(t["id"], output=rel.as_posix())
    office.move_task(t["id"], "review", actor=who)
    office.set_model_now(who, "")
    office.set_status(who, "idle", "")
    office.log(who, f"Nộp phản biện mù {pdf.name} → {rel.as_posix()}", kind="done")
    shutil.rmtree(box, ignore_errors=True)
    print(rel)


if __name__ == "__main__":
    main()
