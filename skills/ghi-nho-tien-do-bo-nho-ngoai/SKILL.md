---
name: ghi-nho-tien-do-bo-nho-ngoai
description: Dùng khi Phòng Game cần lưu tiến độ/ghi chú để phiên sau đọc lại mà thư mục dự án (vd E:\CTFCLANWAR) bị chặn ghi. Dạy chuyển sang thư mục memory ngoài và xin quyền đúng 1 lần.
---

# Ghi nhớ tiến độ vào bộ nhớ ngoài

## Mục tiêu
Giữ được tiến độ giữa các phiên làm việc mà không ghi vào thư mục dự án bị chặn. Chỉ ghi vào đúng một nơi đã được sếp cho phép.

## Nơi lưu
- Thư mục dự án `E:\CTFCLANWAR`: đang bị chặn ghi, đừng thử ghi vào đó.
- Bộ nhớ ngoài (cần sếp cho phép): `C:\Users\Admin\.claude\projects\E--CTFCLANWAR\memory\`
- Chưa được cấp quyền lượt này thì KHÔNG ghi; làm tiếp phần việc khác, đưa nội dung tiến độ vào báo cáo.

## Các bước
1. **Kiểm tra quyền**: lượt này thư có ghi "được sửa file" kèm thư mục memory chưa? Nếu có, sang bước 3.
2. **Xin quyền đúng 1 lần**, đặt ở CUỐI báo cáo (không viết thư xin vào thư mục nào):
   `[CẦN SẾP] Cho phép ghi tiến độ vào C:\Users\Admin\.claude\projects\E--CTFCLANWAR\memory ? (Có / Không – nếu không thì tiến độ chỉ nằm trong báo cáo)`
   Không hỏi lại cùng một thứ. Sếp không đồng ý mà không ghi gì thì dừng phần lưu.
3. **Đọc trước khi ghi**: xem `MEMORY.md` và các file hiện có; trùng chủ đề thì sửa file cũ, không tạo bản mới.
4. **Mỗi file một sự việc**, tên `ten-ngan-gach-ngang.md`:
   ```markdown
   ---
   name: ten-ngan-gach-ngang
   description: một dòng tóm tắt, dùng để quyết định có cần đọc lại không
   metadata:
     type: project
   ---
   Nội dung: đang làm gì, xong gì, còn gì, file liên quan.

   **Why:** lý do/quyết định đã chốt.
   **How to apply:** phiên sau bắt đầu từ đâu.
   ```
   `type`: `project` (tiến độ, ràng buộc), `feedback` (sếp dặn cách làm), `reference` (đường dẫn, link), `user` (sở thích sếp).
5. **Cập nhật chỉ mục** `MEMORY.md`: thêm 1 dòng `- [Tiêu đề](file.md) — gợi ý ngắn`. Không để nội dung hay frontmatter trong chỉ mục.
6. Ngày tháng ghi tuyệt đối (vd 2026-10-29), không viết "hôm qua", "tuần sau".

## Nên / không nên lưu
- Nên: mốc đã xong, quyết định thiết kế, việc dở dang, đường dẫn quan trọng, điều sếp đã sửa.
- Không: mật khẩu, khoá, token, flag; thứ đã có trong code/lịch sử file; ghi chú chỉ dùng trong phiên này.

## Xong khi
- File memory có đủ frontmatter, `MEMORY.md` có dòng trỏ tới, không trùng file cũ.
- Báo cáo nêu tên file đã tạo/sửa.

## Lỗi hay gặp
- Cố ghi vào `E:\CTFCLANWAR` rồi bị chặn lặp lại → đốt lượt; chuyển ngay sang bước 1–2.
- Hỏi quyền nhiều lần hoặc viết thư xin vào thư mục khác.
- Tạo file mới trùng chủ đề thay vì sửa file cũ.
- Quên cập nhật `MEMORY.md` nên phiên sau không tìm thấy.
- Nhớ cũ có thể lỗi thời: trước khi dựa vào đường dẫn/tên hàm trong memory, kiểm tra còn tồn tại.
