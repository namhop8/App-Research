---
name: thiet-ke-thi-nghiem
description: Thiết kế và chạy thí nghiệm đúng chuẩn reviewer Q1: chia dữ liệu không rò rỉ, baseline công bằng, nhiều seed, thống kê, ghi quyết định, giới hạn CPU. Dùng khi thiết kế, cài đặt hoặc chạy thí nghiệm / baseline.
phases: design, experiment, code, results
---
# Thiết kế thí nghiệm

## Trước khi chạy
- Ghi giả thuyết, metric chính, cách chia dữ liệu và tiêu chí thành công vào `DECISIONS.md` TRƯỚC khi nhìn kết quả test. Phân tích nghĩ ra sau đó phải ghi là "exploratory".
- Chia dữ liệu theo đơn vị độc lập (theo host / người dùng / thời gian), không chia ngẫu nhiên từng dòng khi các dòng liên quan nhau.
- Không chọn ngưỡng, prompt, đặc trưng hay luật sau khi đã xem tập test/audit. Nếu lỡ làm thì báo cả số "không có nó".

## Baseline
- Cùng dữ liệu, cùng ngân sách tính toán, cùng mức tune như phương pháp đề xuất.
- Có ít nhất một baseline mạnh và hợp lý nhất mà reviewer sẽ đòi.

## Chạy
- Mỗi job giới hạn 2 thread: `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2`, `torch.set_num_threads(2)`.
- Cố định seed; so sánh thì chạy ≥5 seed.
- Ghi cấu hình, phiên bản thư viện, lệnh chạy và thời gian vào log.
- Kết quả ra `results/` dạng máy đọc (json/jsonl/csv). Bảng và hình trong paper sinh từ đó bằng script, không gõ tay.
- Chi phí / độ trễ đo trên CPU thật với số thread cố định.

## Thống kê
- Báo 95% bootstrap CI cho mọi metric chính.
- So sánh cặp trên cùng mẫu: McNemar chính xác (phân loại) hoặc paired bootstrap / Wilcoxon.
- Muốn nói "tương đương / không khác" phải dùng TOST với biên ghi rõ (vd. ±0.02).
- Ghi rõ cỡ mẫu.

## Báo cáo
Đã chạy gì (lệnh), kết quả (bảng có CI), so với baseline, chỗ nào còn nghi ngờ (rò rỉ? lệch phân phối?), file kết quả nằm ở đâu.
