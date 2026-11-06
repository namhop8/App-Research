---
name: loc-hunk-theo-chu-khi-commit
description: Dùng khi nhiều người/agent cùng sửa một file chưa commit và bạn chỉ muốn commit phần của mình. Dạy tách hunk của mình vào index bằng patch đã lọc (git apply --cached), không dùng git add -p tương tác.
---

# Lọc hunk theo chủ khi commit

## Mục tiêu
Chỉ đưa các hunk của mình vào index, để nguyên phần người khác trong working tree. Không chế độ tương tác (`git add -p`, `git add -i`, `git commit -p` đều cần gõ phím nên không dùng được khi chạy tự động).

## Nguyên tắc
- Không `git add <file>` cả file, không `git checkout/restore/stash/reset --hard` file đó: sẽ mất hoặc cuốn theo phần của người khác.
- Working tree giữ nguyên; chỉ index thay đổi. Việc xong thì phần người khác vẫn hiện là "chưa stage".
- Xác định "của mình" bằng bằng chứng, không đoán: dấu hiệu trong code (tên hàm/symbol/marker mình thêm), khoảng dòng mình ghi nhớ đã sửa, hoặc `git diff` trước/sau lần sửa của mình.

## Các bước
1. **Xem hiện trạng**: `git status --short <file>` và `git diff -U0 <file>`. Đếm hunk, ghi nhận hunk nào của mình.
2. **Xuất patch ra file bằng git, KHÔNG dùng `>` của PowerShell** (PowerShell 5 ghi UTF-16 làm patch hỏng):
   `git diff -U0 --output=.tmp_full.patch -- <file>`
   (`-U0` để mỗi cụm sửa là một hunk riêng, không bị gộp bởi dòng ngữ cảnh.)
3. **Lọc hunk** bằng script Python (mẫu bên dưới), ghi `.tmp_mine.patch`. Chạy `python -I loc_hunk.py ...`.
4. **Kiểm tra khô**: `git apply --cached --unidiff-zero --check .tmp_mine.patch`. Lỗi thì xem mục Lỗi hay gặp.
5. **Đưa vào index**: `git apply --cached --unidiff-zero .tmp_mine.patch`
6. **Soát lại trước khi commit**:
   - `git diff --cached -- <file>` chỉ có phần của mình.
   - `git diff -- <file>` (working vs index) chỉ còn phần người khác.
7. **Commit**: `git commit -m "..."` (không dùng `-a`, không `<file>` ở cuối vì sẽ commit cả file).
8. **Dọn**: xoá `.tmp_*.patch` và script tạm (không để lọt vào commit).

## Mẫu script lọc (loc_hunk.py)
Đặt ngoài thư mục repo hoặc xoá sau khi dùng. Giữ hunk nếu thoả một trong hai: chứa marker, hoặc nằm trong khoảng dòng mới (số dòng của working tree).
```python
import re, sys
# dùng: python -I loc_hunk.py full.patch mine.patch "marker1|marker2" [a-b,c-d]
src, dst, markers = sys.argv[1], sys.argv[2], sys.argv[3]
ranges = []
if len(sys.argv) > 4:
    ranges = [tuple(map(int, r.split("-"))) for r in sys.argv[4].split(",")]
mk = re.compile(markers) if markers else None
text = open(src, encoding="utf-8", newline="").read()
parts = re.split(r"(?m)^(?=@@ )", text)
head, hunks = parts[0], parts[1:]
keep = []
for h in hunks:
    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", h)
    start = int(m.group(1)); n = int(m.group(2) or 1)
    end = start + max(n, 1) - 1
    added = [l for l in h.splitlines()[1:] if l[:1] in "+-"]
    ok = bool(mk) and any(mk.search(l) for l in added)
    ok = ok or any(start <= b and a <= end for a, b in ranges)
    print(("GIỮ " if ok else "BỎ  ") + h.splitlines()[0])
    if ok:
        keep.append(h)
open(dst, "w", encoding="utf-8", newline="").write(head + "".join(keep) if keep else "")
print(f"{len(keep)}/{len(hunks)} hunk")
```
Chạy xong LUÔN đọc danh sách GIỮ/BỎ và đối chiếu với bước 1; không khớp thì chỉnh marker/khoảng dòng, đừng stage.

## Cách thay thế: dựng thẳng bản index (khi patch cứ lỗi)
Lấy bản HEAD, áp phần của mình bằng script/Edit vào bản sao, rồi:
```
git hash-object -w <ban_sao>            # in ra <sha>
git update-index --cacheinfo 100644,<sha>,<duong/dan/file>
```
Dùng khi file là CRLF/LF lẫn lộn hoặc hunk của hai người dính sát nhau.

## Tiêu chí xong
- `git diff --cached` chỉ chứa hunk của mình; `git diff` còn nguyên phần người khác.
- Commit đã tạo, `git status` vẫn báo file "modified" (chưa stage) nếu người khác còn sửa dở.

## Lỗi hay gặp
- **Hai người sửa sát nhau → `-U0` vẫn gộp một hunk**: không tách bằng hunk được. Dùng cách thay thế ở trên, hoặc sửa patch tay (đổi số dòng header) chỉ khi chắc chắn; không chắc thì dừng và hỏi.
- **"patch does not apply"**: thiếu `--unidiff-zero` với `-U0`; hoặc index đã đổi so với lúc xuất patch → xuất lại patch rồi lọc lại.
- **Patch hỏng/rỗng trên PowerShell**: do dùng `>`; dùng `--output=`.
- **CRLF**: mở/ghi với `newline=""` như mẫu; đừng để Python đổi ký tự xuống dòng. Cảnh báo `LF will be replaced by CRLF` chỉ là cảnh báo.
- **Quên rằng người khác sửa tiếp giữa chừng**: bước 2→5 làm liền, không chen việc khác; nếu hunk đổi thì xuất lại.
- **`git commit <file>`** hoặc `-a` kéo cả phần người khác: không dùng.
- Thiếu quyền chạy `git` hoặc ghi file tạm → làm phần đọc/lọc được, rồi ghi `[CẦN SẾP]` đúng 1 lần.
