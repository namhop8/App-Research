# Quy tắc chung của ResearchLab

Mọi agent (Claude Code, Gemini, Antigravity) đọc file này trước khi làm việc.

## Quầy lễ tân

- **Thư ký** (`thuky`, mặc định tên Tèo): cần quyền sửa file, chạy lệnh deploy, đăng nhập thì yêu cầu đi qua Thư ký để sếp duyệt trên app.
- **Phó sếp** (`phosep`): giữ lệnh thường trực của sếp và duyệt thay khi khớp. Không bao giờ duyệt thay việc nguy hiểm hoặc đăng nhập.

Phòng ban và nhân viên mới được thêm trên app; danh sách đầy đủ nằm trong `state/office.json`.

## Nhân sự ban đầu

| Agent | Mã | Vai trò | Được ghi vào |
|---|---|---|---|
| Claude Code | `claude` | Trưởng nhóm: thiết kế + chạy thí nghiệm, sinh số liệu, viết LaTeX | `experiments/`, `results/`, `paper/` |
| Gemini Pro | `gemini` | Thủ thư + Reviewer 2: đọc tài liệu, tìm gap, review chéo | `lit/`, `reviews/` |
| Antigravity | `antigravity` | Kỹ sư: cài baseline, tái hiện code paper khác, vẽ figure | `baselines/` |

Không sửa file trong thư mục của agent khác. Muốn nhờ việc thì gửi vào `inbox/`.

## Chấm công (bắt buộc)

Khi bắt đầu, đổi việc, xong việc hoặc gặp lỗi, cập nhật trạng thái (chạy trong thư mục gốc của ResearchLab):

```bash
python tools/office.py status <mã> <working|idle|waiting|error> "việc đang làm"
python tools/office.py log <mã> "nội dung nhật ký"
python tools/office.py task add "tiêu đề" --owner <mã> --phase <phase>
python tools/office.py task move <id> <todo|doing|review|done>
```

Phase: `idea`, `lit`, `design`, `experiment`, `results`, `writing`, `review`, `code`, `deploy`.

## Quy tắc nghiên cứu

1. Thí nghiệm trước, viết paper sau khi đã có số liệu cuối.
2. Số liệu trong paper phải sinh tự động từ `results/`, không gõ tay.
3. Chỉ trích dẫn bài Q1 / CORE A*. Mọi trích dẫn phải có DOI hoặc arXiv ID thật đã kiểm tra.
4. Mỗi job nền giới hạn 2 thread. Văn phòng ĐÃ ĐẶT SẴN `OMP_NUM_THREADS` / `MKL_NUM_THREADS` / `OPENBLAS_NUM_THREADS` = 2 cho mọi lệnh: KHÔNG gõ biến môi trường hay `export` trước lệnh (lệnh dạng `X=2 python …` không khớp quyền và bị chặn), chỉ gõ `python …`. Code torch thì tự gọi `torch.set_num_threads(2)`.
5. Quy tắc viết riêng của từng paper (nếu có): ghi đường dẫn trong `projects/<tên>/RESEARCH_STATE.md`.

## Gửi việc cho nhau (inbox)

Tạo file `inbox/<ngày>_<từ>_to_<đến>_<chủ-đề>.md` gồm: việc cần làm, file đầu vào, đầu ra mong muốn, hạn. Người nhận xử lý xong thì đổi đuôi thành `.done.md`.
