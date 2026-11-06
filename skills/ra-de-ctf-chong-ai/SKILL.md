---
name: ra-de-ctf-chong-ai
description: Dùng khi thiết kế hoặc rà một đề CTF cần chống LLM/agent giải tự động mà vẫn công bằng với người chơi. Gồm các bước thiết kế, checklist và cách tự thử đề bằng agent.
phases: ctf, security
---

> **Phân vai (sếp chốt 2026-10-24):** người TẠO ĐỀ chỉ tạo gói + viết solve.py, KHÔNG chạy/giải/thử/đăng. Giải để kiểm phải MÙ: văn phòng tự giao Mò (tools/tester.py) khi người tạo đề nộp. Đăng portal là việc của Mít. Các mục chạy lệnh dưới đây dành cho Mò/Mít, người tạo đề đọc để biết gói cần có gì.


# Ra đề CTF chống AI

## Mục tiêu
Đề mà người giỏi giải được trong thời gian hợp lý, còn agent LLM chạy tự động khó giải hoặc tốn rất nhiều lượt. Không cần "chống tuyệt đối". Cần nâng chi phí và thời gian của agent, và đo được điều đó.

## Nguyên tắc
- Đề phải công bằng: chỉ khó với AI vì cần phán đoán, quan sát hoặc tương tác, không vì mập mờ.
- Đừng dựa vào một mẹo duy nhất. Mẹo như "chèn chữ ẩn vào đề" hay "bẫy prompt injection" mất tác dụng nhanh khi mô hình đổi.
- Đề chỉ có giá trị khi đã được thử với agent thật (xem mục "Tự kiểm tra bằng agent").

## Các nhóm kỹ thuật (ưu / nhược)
1. **Nhiều bước, có trạng thái**: server giữ phiên, mỗi bước phụ thuộc kết quả bước trước, có bước phải quan sát rồi mới quyết.
   - Ưu: agent dễ lạc hướng, tốn lượt. Nhược: người chơi cũng mất thời gian. Cần server ổn định.
2. **Cần dữ liệu thật hoặc môi trường động**: dữ liệu sinh ngẫu nhiên theo từng đội, không có đáp án tra được.
   - Ưu: chặn tra writeup cũ. Nhược: tốn công dựng và kiểm.
3. **Cần suy luận dài, ràng buộc chéo** (nhiều điều kiện phải khớp đồng thời, như đồ thị, ràng buộc số học).
   - Ưu: khó đoán mò. Nhược: mô hình mới có thể giải tốt hơn, phải thử lại định kỳ.
4. **Đa phương thức / đồ họa** (đọc ảnh nhiễu, âm thanh, giao diện phải thao tác).
   - Ưu: nhiều agent yếu ở đây. Nhược: dễ bất công với người dùng công cụ hỗ trợ truy cập; mô hình thị giác tiến nhanh.
5. **Giới hạn tốc độ và hạn mức**: mỗi đội chỉ được số lần thử nhất định, có khóa tạm khi sai.
   - Ưu: đánh vào kiểu thử-sai hàng loạt. Nhược: phải chống lách bằng nhiều IP/tài khoản; làm khổ người chơi thật.
6. **Phát hiện chỉ dẫn lạ trong dữ liệu** (agent bị dẫn lệch bởi nội dung trong file/trang). Chỉ dùng như phép thử phụ để xem agent có làm theo chỉ dẫn nhúng hay không, không làm cơ chế chính.

> **Nguồn: đang chờ Gemini** (thư `inbox/2026-10-23_223500_com_to_gemini_nguon-ctf-chong-ai.md`). Phần ưu/nhược trên là kinh nghiệm chung, chưa gắn nguồn ngoài đã kiểm chứng. Khi có nguồn, ghi vào đây kèm DOI/arXiv/URL thật đã kiểm. Đừng chép nguồn từ trí nhớ.

## Các bước
1. Chọn mục tiêu học tập và độ khó cho người chơi (ghi 2-3 dòng).
2. Chọn 1-2 nhóm kỹ thuật phía trên, ưu tiên nhóm 1, 2, 3.
3. Dựng đề trong thư mục riêng, flag là chuỗi giữ chỗ (ví dụ `FLAG{placeholder}`); flag thật cấu hình lúc deploy, không lưu trong repo.
4. Viết lời giải tham chiếu cho người, ghi thời gian giải ước tính.
5. Thử bằng agent (mục dưới).
6. Sửa đề theo kết quả thử, lặp lại tới khi đạt tiêu chí.

## Tự kiểm tra bằng agent
- Cho 2-3 agent/mô hình khác nhau giải, mỗi loại chạy tối thiểu 5 lần, chỉ đưa đề bài như người chơi thấy (không đưa lời giải).
- Ghi lại: số lần giải được, số lượt, thời gian, chỗ agent kẹt.
- Chạy trong môi trường cô lập, chỉ trỏ vào máy chủ thử của đề, không trỏ ra ngoài.
- Mỗi job nền giới hạn 2 thread (`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2`).
- Lưu kết quả thành bảng trong `results/`, không gõ tay vào báo cáo.

## Checklist
- [ ] Người giải được bằng lời giải tham chiếu, đúng thời gian dự kiến
- [ ] Không có đường tắt (đọc mã nguồn, đoán endpoint, đáp án trong writeup cũ)
- [ ] Dữ liệu sinh theo từng đội hoặc từng phiên
- [ ] Có giới hạn tốc độ hợp lý, không làm hỏng trải nghiệm người thật
- [ ] Đã thử với ít nhất 2 loại agent, mỗi loại ≥5 lần
- [ ] Không có flag, khóa, token thật trong repo
- [ ] Có kế hoạch thử lại khi mô hình mới ra

## Tiêu chí xong
Tỷ lệ agent giải thấp theo ngưỡng do ban tổ chức đặt (ví dụ ≤20% số lần chạy) **và** người chơi giải được. Ngưỡng phải ghi rõ, đừng lấy ngưỡng chung chung.

## Lỗi hay gặp
- Làm đề khó với cả người lẫn AI: không còn là đề hay.
- Tin vào "chữ ẩn" hay bẫy prompt: agent mới bỏ qua được, còn người dùng công cụ hỗ trợ truy cập bị thiệt.
- Chỉ thử một lần, một mô hình, rồi kết luận.
- Để lộ đáp án trong log, hint hoặc mã nguồn client.
- Quên đặt lại trạng thái server giữa các lần thử agent, làm kết quả lệch.
