---
name: kiem-chung-trich-dan
description: Kiểm tra từng trích dẫn: bài có thật, đúng venue/hạng, đúng nội dung được dẫn. Dùng khi review bản thảo, related work hoặc danh sách tài liệu.
phases: review, lit, writing
---
# Kiểm chứng trích dẫn

Với mỗi `\cite` (ưu tiên các câu mang tải chính của paper):
1. Bài có thật? Tên, tác giả, năm, venue khớp với DOI/arXiv. Không xác minh được → đánh dấu [CHƯA XÁC MINH].
2. Venue đạt chuẩn? Q1/Q2 hoặc CORE A*/A (hoặc ngoại lệ hợp lệ: dataset, công cụ, chuẩn). Ghi hạng.
3. Câu dẫn nói đúng điều bài gốc nói? Không phóng đại, không gán số liệu bài gốc không có.
4. Khoá trích dẫn có trong file .bib, không trùng, không thiếu trường bắt buộc.
Kết quả: bảng `câu / khoá / venue + hạng / thật? / dẫn đúng? / cần sửa gì`.
