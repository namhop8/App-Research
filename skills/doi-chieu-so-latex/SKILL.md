---
name: doi-chieu-so-latex
description: Trích mọi con số từ LaTeX (macro `\newcommand`, bảng `tab_*.tex`, `\num{}`/`\SI{}`, tuỳ chọn cả văn xuôi) và đối chiếu với file trong `results/` bằng một công cụ dùng chung của phòng. Dùng khi cần chứng minh "số trong paper khớp số liệu" (quy tắc 2), lập `evidence/numbers.md` cho gói nghiệm thu, hoặc sau khi sinh lại bảng.
phases: review, writing, results
---
# Đối chiếu số LaTeX với results/

## Mục tiêu
Mỗi số trong paper truy được về một khoá trong `results/` (quy tắc 2). Việc này do **một công cụ chung** làm, không viết script riêng cho từng paper: `skills/doi-chieu-so-latex/check_numbers.py`. Công cụ chỉ đọc, không sửa `.tex` hay `results/`.

## Các bước
1. **Chuẩn bị.** Số liệu cuối đã nằm trong `results/` (json, jsonl, csv). Bảng `tab_*.tex` đã sinh lại bằng script (xem `goi-nghiem-thu-paper`, bước 2); đối chiếu bảng gõ tay là vô nghĩa.
2. **Chạy** từ `projects/<tên>/` (PowerShell):
```powershell
$env:OMP_NUM_THREADS=2; $env:MKL_NUM_THREADS=2; $env:OPENBLAS_NUM_THREADS=2
python -I E:\ResearchLab\skills\doi-chieu-so-latex\check_numbers.py `
  --tex paper/main.tex paper/macros.tex paper/tab_*.tex `
  --results results/ --prose --out acceptance/evidence/numbers.md
```
   - Không có `--prose`: chỉ lấy số trong macro, bảng, `\num`/`\SI`/`\qty` (nhanh, ít nhiễu).
   - Có `--prose`: lấy thêm số trong văn xuôi (abstract, intro, conclusion). Dùng khi lập bảng cho mục B.
   - Đường dẫn `--tex` nhận glob. `--results` nhận thư mục hoặc một file.
3. **Đọc kết quả** (mỗi dòng: `file:dòng`, loại, nhãn, số, trạng thái, khoá nguồn):
   - `MATCH`: có khoá làm tròn ra đúng số đó (theo đúng số chữ số thập phân đang in; thử cả nhân 100 cho %).
   - `AMBIGUOUS`: số nguyên hoặc >3 ứng viên. Người duyệt tự chỉ khoá đúng và ghi vào cột ghi chú; không coi là đạt.
   - `NO-SOURCE`: không khoá nào sinh ra số này. Hoặc số gõ tay (sửa script sinh, không sửa tay), hoặc số không đến từ thí nghiệm (năm, số RQ, tham số cố định): ghi lý do vào `numbers.md`.
4. **Xử lý.** Mọi `NO-SOURCE` phải về 0 hoặc có lý do ghi rõ. Số có thật nhưng chỉ nằm trong log/ghi chú/bản cũ (Jaccard, audit nhãn, số v1, thời gian đo): làm theo kỹ năng `ghi-so-tu-log-vao-results` để đưa vào `results/`. Số trong abstract/intro/conclusion thì tự mở `results/` kiểm tay ít nhất 3 số (tiêu chí lần 1 của `goi-nghiem-thu-paper`).
5. **Lưu** `numbers.md` vào `acceptance/evidence/` và ghi lệnh đã chạy vào `evidence/repro.md`.

## Macro: quy ước nên theo
Để số trong văn xuôi không bị gõ tay, paper dùng macro sinh tự động:
```latex
% macros.tex  (do script ghi, không sửa tay)
\newcommand{\accMain}{0.847}
\newcommand{\nTest}{\num{12480}}
```
Trong `main.tex` viết `\accMain`, không viết `0.847`. Công cụ bắt số ở nơi macro được định nghĩa, nên mỗi số chỉ cần đối chiếu một lần. Với `--prose`, số còn nằm trần trong văn xuôi vẫn bị liệt kê: đó là chỗ nên đổi sang macro.

## Giới hạn (nói rõ khi báo cáo)
- Khớp theo giá trị làm tròn, không theo ý nghĩa: `MATCH` nghĩa là "có một khoá cho ra số này", chưa chứng minh khoá đó đúng chỉ số. Với mục B, người duyệt vẫn xác nhận khoá đúng chỉ số (ví dụ accuracy, không phải F1).
- Chỉ đọc macro có đối số dạng `{...}` không lồng nhau; macro tính toán (`\pgfmathsetmacro`, `\FPeval`) và số trong hình `fig_*.pdf` không được xử lý. Đối chiếu dữ liệu sinh ra hình.
- Dòng bắt đầu bằng `%`, `\cite`, `\ref`, `\label`, `\input` bị bỏ qua. Số trong `\cite{}` không bị lấy nhưng số trong tên khoá (`smith2024`) thì có thể lọt vào văn xuôi; bỏ qua khi duyệt.
- Mỗi lần có paper dùng cấu trúc lạ (ví dụ `siunitx` với `table-format`), kiểm một bảng bằng tay trước khi tin kết quả.

## Tiêu chí xong
- `numbers.md` được tạo, đầu file có dòng tổng `MATCH/AMBIGUOUS/NO-SOURCE`.
- `NO-SOURCE` = 0 hoặc mỗi dòng có lý do; `AMBIGUOUS` đã được người duyệt chọn khoá.
- Lập lại sau mỗi lần số liệu hoặc bảng đổi (mọi thay đổi sau chữ ký làm gói mất hiệu lực).

## Lỗi hay gặp
- Chạy khi `results/` còn là số tạm: kết quả vô giá trị, đợi số cuối.
- Coi số nguyên (n = 12480) là khớp vì trùng ngẫu nhiên: công cụ gắn `AMBIGUOUS` cho số không có phần thập phân, đừng bỏ qua.
- Bảng in `85.3` còn `results/` lưu `0.853`: công cụ thử nhân 100; nếu bảng làm tròn khác quy ước (cắt thay vì làm tròn) sẽ hiện `NO-SOURCE`, sửa quy ước trong script sinh bảng.
- Số dưới dạng `$-0.5$` hoặc `\num{1{,}234}` đã được xử lý; dạng `1.234,5` (kiểu châu Âu) thì không, hãy thống nhất dùng dấu chấm thập phân.
- Chạy `python` không có `-I` trong thư mục có file lạ: có thể nạp nhầm module cùng tên.
- Sửa `.tex` bằng heredoc/sed làm hỏng dấu `\`: dùng công cụ Write/Edit (xem `viet-paper-q1`, mục 2.4).
