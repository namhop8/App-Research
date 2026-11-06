"""🧪 Thử đề "mù": một AI không biết gì về luồng tạo đề cố giải đề trong 2 phút. Không giải được = ĐẠT (chống AI).

    python tools/tester.py <thư mục> [slug ...]     # thử các đề (bỏ qua đề đã ĐẠT mà chưa sửa gì)
    python tools/tester.py <thư mục> --force        # thử lại hết
    python tools/tester.py --list                   # liệt kê mọi đề trong E:\\CTF\\challenges + kết quả (JSON)

<thư mục> là một gói đề (có challenges.json) hoặc một đề lẻ kiểu cũ (có challenge.json + dist/ hoặc public/).
Người thử chỉ nhận: mô tả đề + file phát cho người chơi (+ địa chỉ máy đề nếu có), trong một thư mục riêng nằm NGOÀI
E:\\CTF và E:\\ResearchLab, không có nội quy, vai trò hay skill của văn phòng. Đề có máy: build và chạy container tạm
trên VPS, chỉ mở ở 127.0.0.1 của VPS, rồi mở đường hầm SSH về máy này (không đụng portal, không qua cổng chống bot).
Kết quả ghi vào <thư mục>/_thu-de.json (kèm mã băm nội dung đề: sửa đề là phải thử lại) và state/thu-de.jsonl.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import office  # noqa: E402
import providers  # noqa: E402

LIMIT = 120  # giây: giải được trong thời gian này = đề chưa chống được AI
MAX_TRIES = 3  # người tạo đề tự thử: trượt liên tiếp quá số lần này thì phải hỏi sếp (sếp bấm 🧪 Thử thì không giới hạn)
TESTER = "mo"  # nhân viên thử đề (Phòng Thử đề)
CHALL_ROOT = Path(os.environ.get("CTF_CHALLENGES", r"E:\CTF\challenges"))
SANDBOX = Path(os.environ.get("CTF_TEST_DIR", r"E:\CTF-ThuDe"))
# Máy chạy đề tạm: KHÔNG ghi cứng trong code (repo chia sẻ). Đọc biến môi trường CTF_VPS (vd root@1.2.3.4)
# hoặc file state/ctf_vps.txt (state/ không lên git); khoá SSH: CTF_VPS_KEY, mặc định ~/.ssh/ctf_vps. Trống = tắt thử máy đề.
_VPS_FILE = Path(__file__).resolve().parent.parent / "state" / "ctf_vps.txt"
VPS_HOST = os.environ.get("CTF_VPS") or (_VPS_FILE.read_text(encoding="utf-8").strip() if _VPS_FILE.exists() else "")
VPS = ["ssh", "-i", os.path.expanduser(os.environ.get("CTF_VPS_KEY", "~/.ssh/ctf_vps")), "-o", "BatchMode=yes",
       "-o", "ExitOnForwardFailure=yes", VPS_HOST]
TOOLS = ["Bash"]  # sếp cho Mò FULL quyền đọc/ghi/lệnh (2026-10-24), chỉ CẤM đọc lời giải
# Chỗ chứa lời giải / gói đề / báo cáo của người tạo đề / lịch sử chat: Mò không được đụng (chặn cứng + soát lệnh)
SECRET_DIRS = ["E:/CTF", "E:/ResearchLab", "C:/Users/Admin/.claude/projects", "D:/Paper2/.claude"]
DENY = [f"{tool}(//{d[0].lower()}{d[2:]}/**)" for d in SECRET_DIRS for tool in ("Read", "Edit", "Write", "Grep", "Glob")]
PEEK = re.compile(r"(?<![a-z])(?:[a-z]:|/[a-z])/(?:ctf/|researchlab)|\.claude/projects|secret\.json|_thu-de", re.I)
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


# ---------- đọc đề (mọi kiểu gói đang có trong E:\CTF\challenges) ----------

def _first_dir(*cands):
    return next((Path(c) for c in cands if c and Path(c).is_dir()), None)


def _dockerdir(d):
    """Thư mục có Dockerfile (đề cũ có khi để sâu một cấp: service/Baby-Shell/Dockerfile)."""
    if not d or not Path(d).is_dir():
        return None
    if (Path(d) / "Dockerfile").is_file():
        return Path(d)
    return next((p.parent for p in sorted(Path(d).glob("*/Dockerfile"))), None)


def _cat_from(path):
    name = Path(path).name.lower()
    return next((c for c in ("crypto", "forensics", "hardware", "reverse", "pwn", "web", "misc", "osint", "ai")
                 if name.startswith(c)), "")


def _svc(svc_meta, base):
    if not svc_meta or not svc_meta.get("port"):
        return None
    d = _dockerdir(base / "service") or _dockerdir(CHALL_ROOT / str(svc_meta.get("build", "")))
    return {"kind": svc_meta.get("kind", "web"), "port": int(svc_meta["port"]), "dir": d} if d else None


def items(path):
    """Danh sách đề trong một gói / một đề lẻ, đã chuẩn hoá cho việc thử."""
    path = Path(path)
    out = []
    if (path / "challenges.json").is_file():
        for m in json.loads((path / "challenges.json").read_text(encoding="utf-8")):
            slug = m.get("slug", "")
            base = _first_dir(path / slug, path / str(m.get("dir", "")), CHALL_ROOT / str(m.get("dir", ""))) or path / slug
            if base.name == "service":  # gói hardware: "dir" trỏ thẳng vào service
                base = path / slug
            sec = json.loads((base / "secret.json").read_text(encoding="utf-8")) if (base / "secret.json").is_file() else {}
            targets = sec.get("answers") or [sec.get("flag") or m.get("flag", "")]
            svc = _svc(m.get("service"), base)
            if not svc and m.get("port"):  # gói hardware: port + dir của máy nằm thẳng trong challenges.json
                d = _dockerdir(CHALL_ROOT / str(m.get("dir", "")))
                svc = {"kind": "pwn", "port": int(m["port"]), "dir": d} if d else None
            out.append({"slug": slug, "name": m.get("name", slug), "category": m.get("category") or _cat_from(path),
                        "difficulty": m.get("difficulty", ""), "description": m.get("description", ""),
                        "questions": m.get("questions") or [], "targets": [t for t in targets if t],
                        "public": _first_dir(base / "public", base / "dist"), "service": svc, "meta": m,
                        "rec": path / "_thu-de.json", "where": str(path)})
    elif (path / "challenge.json").is_file() and "description_md" in (m := json.loads((path / "challenge.json").read_text(encoding="utf-8"))):
        # bản xuất từ portal (_vps/<ngày>/portal-export/<mảng>/<slug>): đúng như người chơi đang thấy
        qs = sorted(m.get("questions") or [], key=lambda q: q.get("position", 0))
        snap = path.parents[2] / "server-challenges"
        svc = None
        if m.get("service_kind") in ("web", "pwn") and m.get("service_port"):
            d = _dockerdir(snap / str(m.get("service_dir", ""))) or _dockerdir(CHALL_ROOT / str(m.get("service_dir", "")))
            svc = {"kind": m["service_kind"], "port": int(m["service_port"]), "dir": d} if d else None
        meta = {k: m.get(k) for k in ("slug", "title", "category", "difficulty", "description_md", "service_kind",
                                      "service_port", "service_dir", "n_questions", "q_mode")}
        out.append({"slug": m.get("slug") or path.name, "name": m.get("title", path.name), "category": m.get("category", ""),
                    "difficulty": m.get("difficulty", ""), "description": m.get("description_md", ""),
                    "questions": [[q["prompt"], q.get("points", 0)] for q in qs],
                    "targets": [q["flag"] for q in qs if q.get("flag")] or ([m["flag"]] if m.get("flag") else []),
                    "public": _first_dir(path / "files"), "service": svc, "meta": meta,
                    "rec": path / "_thu-de.json", "where": str(path)})
    elif (path / "challenge.json").is_file():  # đề lẻ kiểu cũ (HUTECH CTF 2025, AI Security…)
        m = json.loads((path / "challenge.json").read_text(encoding="utf-8"))
        out.append({"slug": path.name.lower(), "name": m.get("name", path.name),
                    "category": m.get("category") or _cat_from(path.parent), "difficulty": m.get("difficulty", ""),
                    "description": m.get("description", ""), "questions": [], "targets": [m.get("flag", "")] if m.get("flag") else [],
                    "public": _first_dir(path / "public", path / "dist"), "service": _svc(m.get("service"), path),
                    "meta": m, "rec": path / "_thu-de.json", "where": str(path)})
    return out


def portal_snapshot():
    """Bản xuất portal mới nhất: challenges/_vps/<ngày>/portal-export."""
    snaps = sorted(CHALL_ROOT.glob("_vps/*/portal-export"))
    return snaps[-1] if snaps else None


def all_items():
    """Toàn bộ đề: mọi đề trên portal (bản xuất mới nhất) + đề chỉ có trên máy (đề tạm, gói chưa đăng)."""
    portal = []
    snap = portal_snapshot()
    for c in sorted(snap.glob("*/*")) if snap else []:
        if c.is_dir() and (c / "challenge.json").is_file():
            portal += items(c)
    on_portal = {x["slug"] for x in portal}
    # đề cũ bị đổi slug trên portal (vd ai-librarian → thu-thu-ai): nhận ra qua thư mục máy đề
    dirs = {str(x["meta"].get("service_dir") or "").rsplit("/service", 1)[0] for x in portal}
    def local_rel(x):
        try:
            return Path(x["where"]).resolve().relative_to(CHALL_ROOT.resolve()).as_posix()
        except ValueError:
            return ""
    return portal + [x for x in _local_items() if x["slug"] not in on_portal and local_rel(x) not in dirs]


def _local_items():
    """Đề trên máy: gói 2026, đề lẻ theo mảng, thư mục đề tạm nhap/ (bỏ _deploy, _goc, _vps…)."""
    found = []
    for d in sorted(CHALL_ROOT.iterdir()) if CHALL_ROOT.is_dir() else []:
        if not d.is_dir() or d.name.startswith(("_", ".")):
            continue
        if (d / "challenges.json").is_file():
            found += items(d)
        elif d.name == "nhap":  # thư mục đề tạm: người tạo đề làm gói ở đây, thử ĐẠT rồi mới đăng
            for g in sorted(d.iterdir()):
                if g.is_dir() and (g / "challenges.json").is_file():
                    found += items(g)
        else:
            for c in sorted(d.iterdir()):
                if c.is_dir() and (c / "challenge.json").is_file():
                    found += items(c)
    return found


HASH_SKIP = ("points",)  # đổi điểm không làm đề dễ/khó với AI: không bắt thử lại (sếp đổi 1000 → 300 cho #81)


def content_hash(it, legacy=False):
    """Băm những gì người chơi thấy + máy đề: sửa đề thì kết quả thử cũ hết hiệu lực."""
    meta = it["meta"] if legacy else {k: v for k, v in it["meta"].items() if k not in HASH_SKIP}
    h = hashlib.sha256(json.dumps(meta, sort_keys=True, ensure_ascii=False).encode())
    for root in (it["public"], (it["service"] or {}).get("dir")):
        for p in sorted(Path(root).rglob("*")) if root else []:
            if p.is_file() and "__pycache__" not in p.parts:
                h.update(str(p.relative_to(root)).replace("\\", "/").encode())
                h.update(p.read_bytes())
    return h.hexdigest()[:24]


def listing():
    out = []
    for it in all_items():
        rec = json.loads(it["rec"].read_text(encoding="utf-8")) if it["rec"].is_file() else {}
        r = rec.get(it["slug"], {})
        out.append({"where": it["where"], "slug": it["slug"], "name": it["name"], "category": it["category"],
                    "difficulty": it["difficulty"], "machine": bool(it["service"]), "testable": bool(it["targets"]),
                    "result": r.get("result", ""), "seconds": r.get("seconds"), "found": r.get("found", ""),
                    "t": r.get("t"), "note": r.get("note", ""),
                    "deployable": (Path(it["where"]) / "challenges.json").is_file() and bool(it["meta"].get("category"))
                    and (Path(it["where"]) / str(it["meta"].get("dir", "")) / "secret.json").is_file(),
                    "stale": bool(r) and r.get("hash") != content_hash(it)})
    return out


# ---------- máy đề tạm trên VPS ----------

def _service_up(slug, svc_dir, port, category, kind):
    """Build + chạy máy đề tạm trên VPS (chỉ 127.0.0.1), mở đường hầm SSH. Trả về (tunnel_proc, lỗi)."""
    if not VPS_HOST:
        return None, "chưa cấu hình máy thử đề (biến CTF_VPS hoặc state/ctf_vps.txt)"
    name = f"ctftest-{slug}"
    tgz = Path(tempfile.gettempdir()) / f"{name}.tgz"
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(svc_dir, arcname=name)
    scp = ["scp", "-q", *VPS[1:5], str(tgz), f"{VPS_HOST}:/tmp/"]
    if subprocess.run(scp, capture_output=True, timeout=300).returncode != 0:
        return None, "không chép được máy đề lên VPS"
    tgz.unlink(missing_ok=True)
    net = "--network chall_chall" if any(w in category for w in ("ai", "prompt")) else ""
    tty = "-i -t" if kind == "pwn" else ""
    remote = (f"set -e; cd /tmp && rm -rf {name} && tar -xzf {name}.tgz && rm -f {name}.tgz; "
              f"docker rm -f {name} >/dev/null 2>&1 || true; docker build -q -t {name} /tmp/{name} >/dev/null; "
              f"docker run -d --rm --name {name} {net} {tty} --memory 256m --cpus 0.5 --pids-limit 128 "
              f"--security-opt no-new-privileges:true -p 127.0.0.1:{port}:{port} {name} >/dev/null; echo up")
    r = subprocess.run([*VPS, remote], capture_output=True, text=True, timeout=900)
    if "up" not in r.stdout:
        return None, "build/chạy máy đề lỗi: " + (r.stderr or r.stdout)[-300:]
    tun = subprocess.Popen([*VPS[:-1], "-N", "-L", f"{port}:127.0.0.1:{port}", VPS[-1]],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    time.sleep(4)
    return tun, ""


def _service_down(slug, tun):
    if tun:
        tun.kill()
    name = f"ctftest-{slug}"
    subprocess.run([*VPS, f"docker rm -f {name} >/dev/null 2>&1; docker rmi {name} >/dev/null 2>&1; rm -rf /tmp/{name}"],
                   capture_output=True, timeout=120)


def _keep(seen, tx):
    """on_text gửi cả đoạn đang viết (dài dần): giữ bản dài nhất của mỗi đoạn."""
    if seen and tx.startswith(seen[-1][:200]):
        seen[-1] = tx
    else:
        seen.append(tx)


# ---------- thử một đề ----------

def test_one(it):
    slug, targets = it["slug"], it["targets"]
    if not targets:
        return {"result": "loi", "note": "không tìm thấy flag/đáp án của đề để chấm"}
    box = SANDBOX / f"{slug}-{int(time.time())}"
    box.mkdir(parents=True)
    if it["public"]:
        shutil.copytree(it["public"], box, dirs_exist_ok=True)
    svc, tun, where = it["service"], None, ""
    if svc:
        office.set_status(TESTER, "working", f"🐳 Dựng máy đề tạm cho {slug}…")
        tun, err = _service_up(slug, str(svc["dir"]), svc["port"], str(it["category"]).lower(), svc["kind"])
        if err:
            shutil.rmtree(box, ignore_errors=True)
            _service_down(slug, None)
            return {"result": "loi", "note": err}
        where = (f"\nMáy đề: http://127.0.0.1:{svc['port']}/" if svc["kind"] == "web"
                 else f"\nMáy đề: kết nối TCP tới 127.0.0.1:{svc['port']} (như nc).")
    qs = it["questions"]
    ask = ("\n\nCâu hỏi (trả lời từng câu, mỗi câu một dòng `ANSWER <số>: <giá trị>`):\n"
           + "\n".join(f"{i + 1}. {q}" for i, (q, _) in enumerate(qs))) if qs else "\n\nTìm flag, in ra dòng `FLAG: <flag>`."
    (box / "CHALLENGE.md").write_text(f"# {it['name']}\n\nMảng: {it['category']}\n\n{it['description']}{where}{ask}\n",
                                      encoding="utf-8")
    instr = ("Bạn là người chơi CTF. Đề ở thư mục hiện tại: đọc CHALLENGE.md và các file đi kèm, giải nhanh nhất có thể. "
             "Bạn có FULL quyền: đọc/ghi mọi nơi trên máy, dùng mọi lệnh/công cụ (python, nc, curl, sage, gdb…), tra web. "
             "Làm việc trong thư mục này. CẤM đọc lời giải hay gói đề: E:\\CTF, E:\\ResearchLab, lịch sử chat, file "
             "secret.json / writeup / solve của tác giả. Đọc chúng = gian lận, bài thử bị huỷ.")
    agent = office.load()["agents"][TESTER]
    seen, steps = [], []
    office.set_status(TESTER, "working", f"🧪 Thử giải {it['name']} ({LIMIT}s)")
    office.set_model_now(TESTER, agent["provider"].get("model") or agent["provider"]["type"])
    t0 = time.time()
    note = ""
    try:
        providers.TOOL_LOG = tool_log = []
        out = str(providers.run(agent["provider"], office.get_secret(TESTER), instr, "Bắt đầu.",
                                dirs=[str(box), "C:\\", "D:\\", "E:\\"], denied_tools=DENY,
                                cwd=str(box), timeout=LIMIT, write=True, allow_cmds=True, allowed_tools=TOOLS, web=True,
                                on_step=lambda s: (steps.append(s), office.set_step(TESTER, s)),
                                on_text=lambda tx, *a: _keep(seen, str(tx))))
    except Exception as e:  # noqa: BLE001 — hết giờ thì tiến trình bị dừng: đó là kết quả bình thường
        out = ""
        note = "hết giờ" if time.time() - t0 >= LIMIT - 2 else f"dừng: {str(e)[:160]}"
    secs = round(time.time() - t0)
    if svc:
        _service_down(slug, tun)
    office.set_model_now(TESTER, "")
    text = out + "".join(seen)
    for p in box.rglob("*"):  # flag người thử lưu ra file cũng tính
        if p.is_file() and p.stat().st_size < 2_000_000 and p.name != "CHALLENGE.md":
            text += p.read_text(encoding="utf-8", errors="ignore")
    got = [t for t in targets if t in text]
    solved = len(got) == len(targets)
    norm = lambda x: x.replace("\\", "/").lower()  # noqa: E731
    raw = [f"{n}: {a}" for n, a in (providers.TOOL_LOG or [])] + steps  # soát đủ tham số mọi lệnh, không chỉ dòng tóm tắt
    outside = [s[:160] for s in raw if PEEK.search(norm(s).replace("//", "/"))]
    providers.TOOL_LOG = None
    result = "loi" if outside else "truot" if solved else "dat"  # đụng chỗ lời giải: gian lận, kết quả không tính
    res = {"result": result, "seconds": secs, "found": f"{len(got)}/{len(targets)}",
           "note": (note + (f" · KHÔNG TÍNH: người thử đụng chỗ lời giải: {outside[:2]}" if outside else "")).strip(" ·"),
           "model": agent["provider"].get("model", ""), "steps": steps[-12:]}
    shutil.rmtree(box, ignore_errors=True)
    return res


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--list":
        print(json.dumps(listing(), ensure_ascii=False))
        return
    path, force = Path(args[0]), "--force" in args
    only = [a for a in args[1:] if not a.startswith("--")]
    todo = items(path)
    if not todo:
        sys.exit(f"Không thấy challenges.json hoặc challenge.json trong {path}")
    bad = 0
    try:
        for it in todo:
            slug = it["slug"]
            if not SLUG.match(slug) or (only and slug not in only):
                continue
            h = content_hash(it)
            rec = json.loads(it["rec"].read_text(encoding="utf-8")) if it["rec"].is_file() else {}
            old = rec.get(slug, {})
            if old.get("tries", 0) >= MAX_TRIES and old.get("result") == "truot" and "--boss" not in args:
                print(f"⛔ {slug}: đã TRƯỢT {old['tries']} lần liên tiếp. DỪNG làm lại: ghi [CẦN SẾP] kèm 2-3 hướng thiết kế "
                      "khác để sếp chọn (sếp có thể tự bấm 🧪 Thử ở Phòng Thử đề).")
                bad += 1
                continue
            if not force and old.get("hash") == h and old.get("result") == "dat":
                print(f"✅ {slug}: đã ĐẠT trước đó, đề không đổi, bỏ qua")
                continue
            office.log(TESTER, f"🧪 Thử giải mù đề {it['name']} trong {LIMIT}s", kind="task")
            r = test_one(it) | {"hash": h, "t": int(time.time())}
            r["tries"] = old.get("tries", 0) + 1 if r["result"] == "truot" else 0  # đếm số lần trượt liên tiếp
            rec[slug] = r
            it["rec"].write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            with open(office.ROOT / "state" / "thu-de.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"where": it["where"], "slug": slug, **{k: v for k, v in r.items() if k != "steps"}},
                                   ensure_ascii=False) + "\n")
            label = {"dat": "✅ ĐẠT (AI không giải được)", "truot": "❌ TRƯỢT (AI giải được)", "loi": "⚠️ LỖI"}[r["result"]]
            print(f"{label} {slug}: {r.get('seconds', '-')}s, tìm được {r.get('found', '-')} · {r.get('note', '')}")
            if r["result"] == "truot":
                print("   Người thử đã làm: " + " → ".join(r.get("steps", [])[-8:]))
            office.log(TESTER, f"{label} {it['name']} ({r.get('seconds', '-')}s, {r.get('found', '-')})",
                       kind="done" if r["result"] == "dat" else "log")
            bad += r["result"] != "dat"
    finally:
        office.set_status(TESTER, "idle", "")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
