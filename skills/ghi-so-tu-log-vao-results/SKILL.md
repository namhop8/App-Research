---
name: ghi-so-tu-log-vao-results
description: Đưa các con số chỉ có trong log, ghi chú hay bản cũ (Jaccard, audit nhãn, số v1, thời gian như 2.5 ms) vào `results/` có nguồn gốc, rồi đổi số gõ tay trong văn xuôi thành macro sinh tự động. Dùng khi `doi-chieu-so-latex` báo `NO-SOURCE` cho số có thật nhưng chưa có file trong `results/`.
phases: results, writing
---
# Ghi số "chỉ có trong log" vào results/

## Mục tiêu
Quy tắc 2: số trong paper phải sinh tự động từ `results/`. Số chỉ nằm trong log hoặc trí nhớ thì chưa có nguồn. Việc ở đây là biến mỗi số thành một khoá trong `results/<tên>.json` kèm dấu vết nguồn, rồi để `macros.tex` do script ghi. Không gõ số vào `.json` hay `.tex` bằng tay.

## Bước 1. Lập danh sách số cần cứu
Chạy `doi-chieu-so-latex` với `--prose`, gom các dòng `NO-SOURCE`. Với mỗi số ghi: vị trí trong `.tex`, ý nghĩa, và **loại nguồn** (bảng dưới). Số không đến từ thí nghiệm (năm, số RQ, tham số cố định) thì khỏi cứu, ghi lý do vào `numbers.md`.

| Loại số | Ví dụ | Cách đưa vào results/ |
|---|---|---|
| A. Log máy sinh còn nguyên | Jaccard in ra stdout | Viết parser đọc log (bước 2A) |
| B. Số tính lại được, rẻ | Jaccard giữa hai tập | Chạy lại bằng script, ghi thẳng json (2B) |
| C. Kết quả đo tay / audit | audit nhãn: số mẫu sai/đúng | Lưu bản ghi thô từng mẫu, tổng do script tính (2C) |
| D. Số của phiên bản cũ | số v1 | Đóng băng, gắn nhãn `v1`, không tính lại (2D) |
| E. Thời gian đo | 2.5 ms | Chạy lại benchmark có kiểm soát (2E) |
| F. Số đếm (cỡ dữ liệu, số mẫu, số cặp) | 78,358; 191 | Đếm lại từ dữ liệu bằng script (2F) |

## Bước 2. Cách xử lý theo loại
Mọi script đặt trong `experiments/` (thư mục của claude), đầu ra trong `results/`.

**2A. Parser log.** Đọc log bằng regex, ghi kèm nguồn:
```python
import re, json, hashlib, pathlib, datetime
log = pathlib.Path("experiments/logs/run_ablation.log")
text = log.read_text(encoding="utf-8")
m = re.search(r"Jaccard\(top-k\)\s*[=:]\s*([0-9.]+)", text)
assert m, "không tìm thấy dòng Jaccard"   # lỗi to hơn là im lặng
out = {"jaccard_topk": float(m.group(1)),
       "_src": {"log": str(log), "line": text[:m.start()].count("\n")+1,
                "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                "extracted": datetime.date.today().isoformat()}}
pathlib.Path("results/jaccard.json").write_text(json.dumps(out, indent=2))
```
Nếu regex khớp nhiều dòng, dùng `finditer` và chọn theo cấu hình rõ ràng, không lấy bừa dòng đầu.

**2B. Tính lại.** Nếu số rẻ để tính, viết `experiments/compute_<tên>.py` đọc đầu vào gốc trong `results/` và ghi json. Ưu tiên cách này hơn parse log vì tái lập được. Đối chiếu với số trong log: lệch thì dừng, tìm nguyên nhân (seed, phiên bản dữ liệu) trước khi dùng.

**2C. Audit nhãn.** Không chỉ lưu tổng. Lưu `results/label_audit.csv` mỗi dòng một mẫu: `id, nhãn_gốc, nhãn_audit, người_audit, ghi_chú`, cùng cách chọn mẫu (seed, cỡ mẫu, tổng thể). Script tính tỉ lệ sai kèm 95% CI (Wilson) ghi vào `results/label_audit.json`. Nếu audit đã làm mà chỉ còn tổng trong ghi chú, nói thẳng trong paper là "tổng hợp từ ghi chú, không có bản ghi từng mẫu" hoặc làm lại audit; không dựng bản ghi giả cho khớp tổng.

**2D. Số v1.** Chép nguyên văn từ nguồn cũ (log/báo cáo v1) vào `results/v1_numbers.json`, mỗi số có `_src` (file, dòng hoặc trang, sha256 nếu là file). Đặt tên khoá có tiền tố `v1_`. Trong paper luôn nói rõ đây là số phiên bản trước, và không so sánh trực tiếp với v2 nếu dữ liệu, split hay metric đã đổi. Không tìm được nguồn gốc của số v1 thì bỏ khỏi paper.

**2E. Thời gian (vd 2.5 ms).** Số đo thời gian từ log đơn lẻ không đủ tin. Chạy lại `experiments/bench_<tên>.py`:
- `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=2`, `torch.set_num_threads(2)` (quy tắc 4).
- Khởi động 20 lần bỏ đi, rồi đo >= 200 lần; ghi median, IQR, p95, đơn vị, cỡ batch.
- Ghi CPU/GPU, hệ điều hành, phiên bản thư viện vào `_env`.
Paper viết "median 2.5 ms" chỉ khi median đo lại làm tròn ra 2.5. Lệch thì dùng số mới.
Quy trình đầy đủ (ghim core, kiểm soát nhiễu, mẫu script, `_env`): xem kỹ năng `do-thoi-gian-cpu`.

**2F. Số đếm (vd 78,358 hay 191).** Đừng chép từ log. Viết `experiments/count_<tên>.py` đếm trực tiếp từ dữ liệu/tập kết quả (số dòng, số id duy nhất, sau lọc nào), ghi `results/counts.json` với `_src` và định nghĩa đếm (`filter`, `unique_by`). Đối chiếu với số trong log: lệch thì dừng, tìm nguyên nhân (trùng lặp, bước lọc) rồi mới dùng. Macro dùng định dạng nghìn (`\num{}`), json lưu số nguyên thô. Nếu dữ liệu gốc không còn để đếm lại, xử lý như 2D: chép nguyên văn từ log kèm `_src`, và ghi rõ trong báo cáo là chưa tái lập.

## Bước 3. Sinh macro, thay văn xuôi
1. Mở rộng script sinh `paper/macros.tex` (script đã có, không viết tay file này) để đọc các json mới:
```python
rows = {"jaccardTopk": j["jaccard_topk"], "auditErrRate": a["err_rate"]}
fmt = {"jaccardTopk": "{:.3f}", "auditErrRate": "{:.1%}"}
```
   Mỗi macro một định dạng cố định, định nghĩa ở một chỗ.
2. Trong `main.tex` thay `0.62` bằng `\jaccardTopk`. Sửa bằng công cụ Edit/Write, không dùng sed/heredoc (hỏng dấu `\`).
3. Chạy lại `check_numbers.py --prose`. Các số vừa cứu phải thành `MATCH`; số nguyên còn `AMBIGUOUS` thì người duyệt chỉ khoá.

## Tiêu chí xong
- Mỗi số cứu được có khoá trong `results/*.json` với `_src` (hoặc CSV thô cho audit), mở ra truy được về log/dòng/lệnh.
- `NO-SOURCE` của các số này bằng 0; văn xuôi dùng macro.
- Số lệch giữa log và tính lại, hoặc không tái lập được, đã được ghi trong báo cáo, không lặng lẽ chọn số đẹp hơn.
- Có dòng trong `evidence/repro.md`: lệnh parser/benchmark đã chạy.

## Lỗi hay gặp
- Chép số từ log vào `macros.tex` bằng tay "cho nhanh": phá quy tắc 2, và lần sau số đổi sẽ lệch.
- Parser regex khớp nhầm dòng của lần chạy khác (log nối nhiều run): kiểm `line` và cấu hình ngay trên dòng đó.
- Quên làm tròn nhất quán: json lưu giá trị thô, làm tròn chỉ ở bước sinh macro.
- Tính Jaccard trên tập khác với log (top-k khác, bỏ trùng hay không): ghi định nghĩa vào json (`k`, tập A, tập B).
- Dùng số v1 như thể là kết quả hiện tại.
- Số thời gian đo khi máy đang chạy job khác hoặc quá 2 thread: đo lại.
