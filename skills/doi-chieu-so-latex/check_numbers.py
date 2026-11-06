#!/usr/bin/env python3
"""Cong cu chung: trich so tu LaTeX (macro, bang, \\num{}) va doi chieu voi results/.

Dung:
  python check_numbers.py --tex paper/main.tex paper/tab_*.tex --results results/ [--prose] [--out numbers.md]

Chi doc file, khong sua gi. Exit code 1 neu con so NO-SOURCE (de gan vao kiem tra tu dong).
"""
import argparse
import csv
import glob
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
MACRO_DEF = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[\d\])?\s*\{([^{}]*)\}"
    r"|\\def\\([A-Za-z]+)\s*\{([^{}]*)\}"
)
NUM_CMD = re.compile(r"\\(?:num|SI|si|qty|pgfmathprintnumber|FPeval)\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}")
SKIP_LINE = re.compile(r"^\s*(%|\\(?:cite|ref|cref|Cref|label|input|include|usepackage|bibliography))")


def clean(s):
    s = s.replace("{,}", "").replace("\\,", "").replace("\\!", "").replace("~", "")
    s = re.sub(r"\\(?:textbf|textit|emph|mathbf|underline)\s*\{([^{}]*)\}", r"\1", s)
    s = s.replace("$", "").replace("\\%", "").replace("%", "").replace("\\pm", " ")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    return s


def numbers_in(s):
    for m in NUM.finditer(clean(s)):
        txt = m.group(0)
        try:
            yield txt, Decimal(txt)
        except InvalidOperation:
            continue


def extract(tex_path, prose):
    """Tra ve list (file, line, kind, label, token, Decimal)."""
    out = []
    text = Path(tex_path).read_text(encoding="utf-8", errors="replace").splitlines()
    in_tab = False
    for i, line in enumerate(text, 1):
        if SKIP_LINE.match(line):
            continue
        code = line.split("%")[0] if "\\%" not in line else line
        for m in MACRO_DEF.finditer(code):
            name, val = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            for tok, d in numbers_in(val):
                out.append((tex_path, i, "macro", "\\" + name, tok, d))
        for m in NUM_CMD.finditer(code):
            for tok, d in numbers_in(m.group(1)):
                out.append((tex_path, i, "num", "\\num", tok, d))
        if re.search(r"\\begin\{(tabular|tabularx|longtable|tabulary)", code):
            in_tab = True
        if in_tab and "&" in code:
            cells = code.split("\\\\")[0].split("&")
            label = cells[0].strip()[:30]
            for c in cells[1:]:
                for tok, d in numbers_in(c):
                    out.append((tex_path, i, "table", label, tok, d))
        if re.search(r"\\end\{(tabular|tabularx|longtable|tabulary)", code):
            in_tab = False
        if prose and not in_tab and not MACRO_DEF.search(code):
            body = NUM_CMD.sub(" ", code)
            body = re.sub(r"\\[A-Za-z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", lambda mm: " " if re.match(r"\\(cite|ref|cref|Cref|label)", mm.group(0)) else mm.group(0), body)
            for tok, d in numbers_in(body):
                out.append((tex_path, i, "prose", "", tok, d))
    return out


def flatten(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{path}[{i}]")
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        yield path, Decimal(str(obj))
    elif isinstance(obj, str):
        try:
            yield path, Decimal(obj)
        except InvalidOperation:
            return


def load_results(root):
    vals = []
    root = Path(root)
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    for p in files:
        rel = str(p).replace("\\", "/")
        try:
            if p.suffix == ".json":
                for k, v in flatten(json.loads(p.read_text(encoding="utf-8"))):
                    vals.append((f"{rel}:{k}", v))
            elif p.suffix == ".jsonl":
                for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if ln.strip():
                        for k, v in flatten(json.loads(ln)):
                            vals.append((f"{rel}:L{n}.{k}", v))
            elif p.suffix == ".csv":
                with p.open(encoding="utf-8", newline="") as f:
                    for n, row in enumerate(csv.DictReader(f), 2):
                        for k, s in row.items():
                            try:
                                vals.append((f"{rel}:L{n}.{k}", Decimal(s)))
                            except (InvalidOperation, TypeError):
                                pass
        except (OSError, ValueError) as e:
            print(f"CANH BAO: khong doc duoc {rel}: {e}", file=sys.stderr)
    return vals


def rnd(x, places):
    return x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def match(tex_val, tok, results):
    places = len(tok.split(".")[1]) if "." in tok else 0
    hits = []
    for key, v in results:
        for scale, tag in ((Decimal(1), ""), (Decimal(100), " (x100, %)")):
            if rnd(v * scale, places) == tex_val:
                hits.append(key + tag)
                break
    return places, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", nargs="+", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--prose", action="store_true", help="lay ca so trong van xuoi (abstract, intro, conclusion)")
    ap.add_argument("--out")
    a = ap.parse_args()

    files = [f for pat in a.tex for f in (glob.glob(pat) or [pat])]
    results = load_results(a.results)
    if not results:
        sys.exit("Khong doc duoc gia tri nao tu results/")
    rows, counts = [], {"MATCH": 0, "AMBIGUOUS": 0, "NO-SOURCE": 0}
    for f in files:
        for (path, ln, kind, label, tok, d) in extract(f, a.prose):
            places, hits = match(d, tok, results)
            if not hits:
                st = "NO-SOURCE"
            elif places == 0 or len(hits) > 3:
                st = "AMBIGUOUS"  # so nguyen hoac qua nhieu ung vien: nguoi duyet phai chon khoa dung
            else:
                st = "MATCH"
            counts[st] += 1
            shown = "; ".join(hits[:3]) + (f" (+{len(hits)-3})" if len(hits) > 3 else "")
            rows.append(f"| {path.replace(chr(92), '/')}:{ln} | {kind} | {label} | {tok} | {st} | {shown} |")

    head = ["| Vi tri | Loai | Nhan | So trong tex | Ket qua | Nguon trong results/ |", "|---|---|---|---|---|---|"]
    summ = f"MATCH={counts['MATCH']}  AMBIGUOUS={counts['AMBIGUOUS']}  NO-SOURCE={counts['NO-SOURCE']}  (tong {len(rows)})"
    text = summ + "\n\n" + "\n".join(head + rows) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(summ)
    if not a.out:
        print(text)
    sys.exit(1 if counts["NO-SOURCE"] else 0)


if __name__ == "__main__":
    main()
