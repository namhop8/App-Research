---
name: goi-nghiem-thu-paper
description: Mẫu chuẩn "gói nghiệm thu paper" (danh mục bắt buộc + tiêu chí ký nhận) để trình duyệt một paper trước khi nộp, kèm quy trình kiểm máy móc cho mục A-C (sha256 hàng loạt, diff bảng sinh tự động, build LaTeX có kiểm log). Dùng khi paper đã có số liệu cuối và cần đóng gói cho trưởng phòng duyệt lần 1, Phó sếp duyệt lần 2, rồi sếp ký.
phases: review, writing, results
---
# Gói nghiệm thu paper

## Mục tiêu
Mỗi paper khi trình duyệt đều đi kèm **một gói giống nhau**, để người duyệt biết chính xác cần mở file nào, kiểm gì, và ký theo tiêu chí nào. Gói này **không thay** việc review nội dung: chạy `review-paper` trước, gói chỉ dẫn tới báo cáo đó.

Điều kiện mở gói: thí nghiệm đã xong, số liệu cuối đã nằm trong `results/` (quy tắc 1: thí nghiệm trước, viết paper sau).

## Vị trí và tên
```
projects/<tên>/acceptance/
  ACCEPTANCE.md        # phiếu nghiệm thu (mẫu bên dưới), file duy nhất người duyệt cần mở đầu tiên
  evidence/            # log build, kết quả lint, bảng đối chiếu số, danh sách trích dẫn đã kiểm
```
Không sao chép file nguồn vào gói; chỉ **trỏ đường dẫn**. Nguồn sự thật vẫn là `paper/`, `results/`, `projects/<tên>/RESEARCH_STATE.md`.

## Danh mục bắt buộc (A-H)
Thiếu bất kỳ mục nào là gói chưa hợp lệ, không được trình duyệt.

| Mã | Hạng mục | Bằng chứng phải có | Đường dẫn mẫu |
|---|---|---|---|
| A | Bản thảo + build sạch | PDF, `main.tex`, log build: 0 lỗi, 0 undefined, số trang trong giới hạn | `paper/`, `evidence/build.log` |
| B | Số liệu sinh tự động | Mỗi bảng/hình có script sinh; bảng đối chiếu >=10 số trong abstract/intro/conclusion với `results/` | `results/`, `evidence/numbers.md` |
| C | Tái lập | Lệnh chạy lại từ đầu, seed, phiên bản thư viện, `OMP/MKL/OPENBLAS_NUM_THREADS=2` và `torch.set_num_threads(2)` | `experiments/`, `evidence/repro.md` |
| D | Trích dẫn | Danh sách mọi cite kèm venue, hạng Q1/CORE A*, DOI hoặc arXiv ID đã mở kiểm; câu cite đã đối chiếu nguồn | `evidence/refs.md` (dùng `kiem-chung-trich-dan`, `xac-thuc-xep-hang-venue`) |
| E | Review chéo | Báo cáo của Gemini (Reviewer 2) và danh sách W1..Wn kèm trạng thái đã xử lý / lý do không sửa | `reviews/`, `evidence/review_status.md` |
| F | Baseline | Baseline do Antigravity cài, ngân sách và tuning ngang bằng, nêu rõ bản code gốc | `baselines/` |
| G | Trung thực kết quả | Kết quả âm đã báo cáo; quyết định sau khi xem test đã công bố; mục Threats to validity | `evidence/honesty.md` |
| H | Hồ sơ nộp | Highlights, CRediT, khai báo AI, competing interest, funding, data availability, affiliation | `evidence/submission.md` |

## Mẫu `ACCEPTANCE.md`
```markdown
# Phiếu nghiệm thu: <tên paper>
- Ngày lập: <YYYY-MM-DD>   Người lập: <mã nhân viên>   Phiên bản bản thảo: <hash hoặc ngày build>
- Venue dự kiến: <tên, hạng>   Hạn nộp: <ngày>

## Tóm tắt (<=5 dòng)
<claim chính, số liệu then chốt, điểm còn vướng>

## Danh mục
| Mã | Có đủ? (Y/N) | Đường dẫn bằng chứng | Ghi chú |
|---|---|---|---|
| A | | | |
... (đủ A-H)

## Vấn đề còn mở
<mỗi dòng: mô tả, vị trí file:line, ai xử lý, hạn. Nếu không có: "Không có">

## Chữ ký (theo thứ tự, không nhảy bước)
| Cấp | Người | Kết quả (Đạt / Chưa đạt) | Lý do nếu chưa đạt | Ngày |
|---|---|---|---|---|
| Duyệt lần 1 | Trưởng phòng | | | |
| Duyệt lần 2 | Phó sếp | | | |
| Ký duyệt | Sếp | | | |
```

## Tiêu chí ký nhận
**Lần 1 - Trưởng phòng (kiểm đủ và đúng):**
1. Đủ A-H, mỗi mục có đường dẫn mở được thật.
2. Tự chạy lại ít nhất 3 số bất kỳ từ `results/` ra khớp với bản thảo.
3. Bản thảo không còn `\pending`, chữ đỏ, en/em dash (theo `viet-paper-q1`).
4. Mọi W mức nặng ở mục E đã sửa hoặc có lý do ghi rõ.

**Lần 2 - Phó sếp (kiểm khớp lệnh sếp):**
1. Title, RQ, claim trong abstract khớp hướng sếp đã giao; không có câu đi ngược title.
2. Quy tắc riêng của paper trong `projects/<tên>/RESEARCH_STATE.md` được tuân thủ.
3. Không có việc nguy hiểm hay ngoài phạm vi chưa được duyệt (nộp bài, đăng nhập hệ thống nộp luôn qua Thư ký để sếp duyệt).

**Cuối - Sếp ký:** chỉ nhận gói đã Đạt cả hai lần. Việc nộp lên hệ thống bên ngoài do sếp quyết định, không ai tự nộp.

## Kiểm máy móc cho A, B, C
Chạy từ `projects/<tên>/` (PowerShell). Mỗi bước ghi kết quả vào `acceptance/evidence/`. Đặt `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=2` trước khi chạy script sinh bảng.

**1. sha256 hàng loạt (B, C):** lập danh sách băm lúc đóng gói, kiểm lại lúc duyệt và ngay trước khi ký.
```powershell
# Lập: băm results/ và nguồn paper/ (bỏ thư mục build), đường dẫn tương đối, dấu /
Get-ChildItem results, paper -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/]build' } |
  ForEach-Object { "{0}  {1}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(), ((Resolve-Path -LiteralPath $_.FullName -Relative) -replace '\\','/' -replace '^\./','') } |
  Set-Content -Encoding utf8 acceptance/evidence/SHA256SUMS
# Kiểm: chịu được đường dẫn có "/" lẫn "\", dấu "*" kiểu sha256sum, dòng trống, CRLF.
# In BAD-LINE / MISSING / MISMATCH cho từng file lệch, bad=0 mới đạt
$bad = 0
Get-Content -Encoding UTF8 acceptance/evidence/SHA256SUMS | Where-Object { $_.Trim() } | ForEach-Object {
  if ($_ -notmatch '^([0-9a-fA-F]{64}) [ *](.+?)\s*$') { "BAD-LINE  $_"; $bad++; return }
  $h = $Matches[1].ToLower(); $p = $Matches[2] -replace '\\','/'
  if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { "MISSING  $p"; $bad++ }
  elseif ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() -ne $h) { "MISMATCH $p"; $bad++ }
}
"bad=$bad" | Tee-Object acceptance/evidence/sha_check.log
# Phát hiện file MỚI chưa có trong danh sách (thêm sau khi lập gói): in EXTRA, cũng tính là lệch
$listed = Get-Content -Encoding UTF8 acceptance/evidence/SHA256SUMS | ForEach-Object { if ($_ -match '^[0-9a-fA-F]{64} [ *](.+?)\s*$') { $Matches[1] -replace '\\','/' } }
Get-ChildItem results, paper -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/]build' } | ForEach-Object {
  $r = (Resolve-Path -LiteralPath $_.FullName -Relative) -replace '\\','/' -replace '^\./',''
  if ($r -notin $listed) { "EXTRA    $r" }
} | Tee-Object -Append acceptance/evidence/sha_check.log
```
Đạt khi `bad=0` và không có dòng `EXTRA`. Một file lệch nghĩa là số liệu hoặc nguồn đã đổi sau khi lập gói: lập lại gói, duyệt lại từ lần 1.
Danh sách do công cụ khác lập (Git Bash `sha256sum`, `certutil`) cũng kiểm được bằng đoạn trên nếu có dạng `<64 hex>  <đường dẫn>`; dòng khác dạng ra `BAD-LINE`. Dùng `-LiteralPath` để tên file có `[ ]` không bị hiểu thành wildcard. Tên file có dấu tiếng Việt: lập danh sách bằng `-Encoding utf8` (PowerShell 5.1 sẽ ghi BOM, đoạn kiểm vẫn đọc được) thay cho `ascii`, nếu không tên sẽ thành `?` và báo MISSING.

**2. Diff bảng sinh tự động (B):** sinh lại mọi bảng vào thư mục tạm rồi so với bảng đang nằm trong `paper/`.
```powershell
$t = Join-Path $env:TEMP 'accept_tables'; New-Item -ItemType Directory -Force $t | Out-Null
# Sinh lại bằng đúng script của paper; chỉ ghi vào $t (nếu script cố định thư mục đích, backup tab_*.tex trước)
$env:OMP_NUM_THREADS=2; $env:MKL_NUM_THREADS=2; $env:OPENBLAS_NUM_THREADS=2
# ví dụ: python <đường dẫn>/tables.py <tên-bảng>   (lặp cho từng bảng)
Get-ChildItem paper/tab_*.tex | ForEach-Object {
  $new = Join-Path $t $_.Name
  if (-not (Test-Path $new)) { "KHONG-SINH-LAI $($_.Name)" }
  elseif ((Get-Content $_ -Raw) -replace "`r`n","`n" -ne ((Get-Content $new -Raw) -replace "`r`n","`n")) { "LECH $($_.Name)" }
} | Tee-Object acceptance/evidence/table_diff.log
```
Đạt khi log rỗng. Bảng `KHONG-SINH-LAI` là bảng gõ tay (vi phạm quy tắc 2): sửa script, không sửa tay file `.tex`. Bảng `LECH`: xem `diff` từng dòng, báo rõ số nào khác. Hình `fig_*.pdf` không so byte (PDF chứa timestamp); so file dữ liệu sinh ra hình.

**3. Build LaTeX có kiểm log (A):** build trong bản sao sạch, không build đè lên `paper/`.
```powershell
$b = Join-Path $env:TEMP 'accept_build'
if (Test-Path $b) { Remove-Item $b -Recurse -Force }
Copy-Item paper $b -Recurse; Push-Location $b
pdflatex -interaction=nonstopmode main.tex; bibtex main; pdflatex -interaction=nonstopmode main.tex; pdflatex -interaction=nonstopmode main.tex
Pop-Location
$log = Get-Content "$b/main.log"
@(
  "loi(^!)      = " + @($log | Select-String '^!').Count
  "undefined    = " + @($log | Select-String 'undefined').Count
  "rerun        = " + @($log | Select-String 'Rerun to get').Count
  "overfull     = " + @($log | Select-String 'Overfull \\hbox').Count
  "bibtex_warn  = " + @(Select-String 'Warning--|error message' "$b/main.blg").Count
  ($log | Select-String 'Output written on').Line
) | Tee-Object acceptance/evidence/build.log
```
Nếu `main.tex` nạp bảng/hình bằng đường dẫn ra ngoài `paper/` (ví dụ `../results/...`), bản sao tạm sẽ báo lỗi file không thấy: sao chép cả thư mục đó vào đúng vị trí tương đối, đừng sửa `.tex` cho khớp. Nếu `main.log` không tồn tại thì pdflatex chưa chạy được: coi là chưa đạt, đừng đọc ra "0 lỗi".
Đạt khi lỗi, undefined, rerun, bibtex_warn đều bằng 0 và số trang trong dòng `Output written` nằm trong giới hạn venue. Overfull: 0 ở bảng và hình; ở đoạn văn thì liệt kê vị trí vào "Vấn đề còn mở". Cũng grep nguồn: `\pending`, `textcolor{red}`, ký tự `–` `—` phải bằng 0. Build tới lần 3 mà vẫn còn `Rerun` là vòng lặp tham chiếu, phải sửa chứ không build thêm.

## Quy trình và trả về
1. Người lập (thường là `claude`) tạo gói, tự đối chiếu A-H, rồi giao trưởng phòng.
2. **Chưa đạt ở bước nào**: người duyệt ghi vào cột "Lý do" **vấn đề cụ thể** (mục nào, file:line, cần làm gì). Gói trả về người lập, sửa xong lập phiếu mới (giữ phiếu cũ, đổi tên `ACCEPTANCE.v1.md`...), và **duyệt lại từ lần 1**.
3. Việc cần nhờ agent khác (review, baseline) gửi qua `inbox/<ngày>_<từ>_to_<đến>_<chủ-đề>.md`, không tự ghi vào thư mục của họ.

## Lỗi hay gặp
- Chỉ ghi "đã kiểm" mà không có đường dẫn bằng chứng: coi như chưa kiểm.
- Bảng đối chiếu số gõ tay: phải sinh từ script đọc `results/` (quy tắc 2).
- Lập gói trước khi có số liệu cuối, dẫn tới đổi số làm hỏng mọi mục B.
- Trích dẫn có venue nhưng chưa mở DOI/arXiv ID thật.
- Sửa bản thảo sau khi đã Đạt lần 1 mà không duyệt lại: mọi thay đổi sau chữ ký đều làm gói mất hiệu lực.
- Băm file PDF vừa build lại rồi so với PDF cũ: PDF chứa timestamp nên luôn lệch. Băm nguồn (`results/`, `.tex`, `.bib`), so log build chứ không so byte PDF.
- Danh sách băm chứa đường dẫn tuyệt đối (`C:\Users\...`) hoặc `.\`: máy khác kiểm ra MISSING hàng loạt. Luôn lưu đường dẫn tương đối, dấu `/`, tính từ `projects/<tên>/`.
- Khác kết thúc dòng CRLF/LF làm diff báo lệch giả: chuẩn hóa về LF trước khi so (như lệnh ở bước 2).
- Build ngay trong `paper/`: file `.aux/.log` sinh ra làm đổi sha256 nguồn. Luôn build ở bản sao tạm.
- Đưa mật khẩu, token hệ thống nộp vào phần H: chỉ ghi "đã khai báo", không ghi thông tin đăng nhập.
