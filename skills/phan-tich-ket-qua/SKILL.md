---
name: phan-tich-ket-qua
description: Đọc và diễn giải kết quả thí nghiệm trung thực: so với baseline có CI, tách phát hiện chính và phụ, nêu giới hạn, đề xuất thí nghiệm tiếp. Dùng khi tổng hợp kết quả, viết finding hoặc RQ Answer.
phases: results, writing, review
---
# Phân tích kết quả

1. Mỗi con số phải chỉ ra được file nguồn trong `results/` (đường dẫn + khoá). Không có nguồn thì không dùng.
2. So với baseline bằng hiệu số kèm 95% CI; hiệu số mà CI cắt 0 thì nói "không khác biệt có ý nghĩa", không nói "tốt hơn".
3. Tách: phát hiện chính (trả lời RQ) / phát hiện phụ / kết quả âm. Kết quả âm vẫn báo, viết thành phát hiện có ích.
4. Kiểm tra lại trước khi tin kết quả quá đẹp: rò rỉ dữ liệu? metric thiên vị phương pháp mình? baseline bị tune kém?
5. Mỗi RQ kết thúc bằng một ô **RQ Answer** 1-3 câu, claim không vượt quá bằng chứng.
6. Đề xuất bước tiếp: thí nghiệm nào sẽ củng cố hoặc bác bỏ phát hiện yếu nhất.
