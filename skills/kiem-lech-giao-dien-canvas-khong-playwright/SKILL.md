---
name: kiem-lech-giao-dien-canvas-khong-playwright
description: Xác nhận chỗ lệch giao diện canvas (chữ tràn khung, đè nút, lệch toạ độ) khi phòng KHÔNG được chạy Playwright. Dùng khi cần kết luận "lệch hay không" bằng đo trong mã, hoặc soạn lệnh một dòng cho Tôm chụp thay.
---
# Kiểm lệch giao diện canvas khi không có Playwright

## Mục tiêu
Ra kết luận có bằng chứng về một chỗ lệch (chữ vs khung, nút vs nút) mà không chạy trình duyệt. Có 3 mức bằng chứng; luôn nói rõ mình đạt mức nào, không viết "đã xác nhận trong game" khi mới ở mức 1-2.

| Mức | Cách | Độ tin |
|---|---|---|
| 1 | Đo trong mã: cỡ chữ, khung, toạ độ | ước lượng, đủ để nghi/loại trừ |
| 2 | Đo bằng `measureText` thật (do Tôm/sếp chạy hoặc test có sẵn) | số thật, chưa thấy hình |
| 3 | Ảnh Tôm chụp, mình mở xem | bằng chứng cuối |

## Bước 1. Gom số liệu từ mã (mức 1, đọc file, không chạy lệnh)
Với mỗi chữ nghi lệch, ghi vào bảng:
- Chuỗi thật (kể cả tên dài, dấu tiếng Việt, số lớn nhất có thể), lấy từ nội dung/catalog, không lấy chuỗi ngắn nhất.
- `fontSize`, `fontFamily`, `fontStyle`, `wordWrap.width`, `padding`, `setScale`/`setDisplaySize`, `lineSpacing`.
- Khung chứa: toạ độ + kích thước của hình/ảnh nền (đọc từ mã, hoặc kích thước PNG trong `assets/`), gốc `setOrigin`, `scale` của container cha, `Scale mode` của game (độ phân giải nội bộ so với 1280×720).
- Mọi phép nhân tỉ lệ dồn lại: kích thước hiệu dụng = cỡ khai × scale của từng cấp cha.

Ước lượng bề rộng: chữ không đều rộng ≈ `0.5–0.6 × fontSize` mỗi ký tự (sans-serif), chữ đậm/hoa ≈ `0.65–0.7`, monospace ≈ `0.6`. Kết luận "chắc chắn lệch" chỉ khi vượt khung ≥20% theo cận trên; "chắc chắn ổn" khi còn dư ≥20% theo cận trên; ở giữa thì cần mức 2 hoặc 3.

Lệch chiều dọc: số dòng sau wrap × (`fontSize` × ~1.2 + `lineSpacing`) so với chiều cao khung.

## Bước 2. Đo thật bằng `measureText` (mức 2)
Nếu dự án có test (vitest/jest) chạy được: thêm test đo, không cần mở trình duyệt hình. Nếu không chạy được lệnh, soạn sẵn và xin ĐÚNG 1 lần.

Mẫu đo trong console game (`?debug=1`), Tôm hoặc sếp dán vào:
```js
(() => { const c = document.createElement('canvas').getContext('2d');
  c.font = '16px "TênFont"';                       // lấy đúng từ mã
  return ['Chuỗi dài nhất 1','Chuỗi dài nhất 2'].map(s => [s, Math.round(c.measureText(s).width)]); })()
```
Hoặc đo thẳng đối tượng Phaser đang hiện: `game.scene.getScenes(true)[0].children.list.filter(o=>o.type==='Text').map(o=>[o.text.slice(0,20), Math.round(o.getBounds().width), Math.round(o.getBounds().height)])`. So với khung ở Bước 1. Tên API đổi theo phiên bản: kiểm trong mã trước khi dán.

Lưu ý: `measureText` phải chạy SAU khi font đã tải, nếu không ra số của font dự phòng.

## Bước 3. Nhờ Tôm chụp bằng lệnh một dòng (mức 3)
Gửi `inbox/<ngày>_<từ>_to_tom_<chủ-đề>.md` (hoặc dòng `[CẦN SẾP]`). Lệnh phải chạy nguyên văn, không biến môi trường, không `export`:
```
python tools/shot.py "http://localhost:8123/?scene=<Màn>&seed=42&debug=1" shots/<việc>/after_<màn>.png 2000
```
Trong thư phải có đủ:
- Màn cần chụp + cách vào (URL/phím/toạ độ), tài khoản tên mới.
- Viewport 1280×720, `device_scale_factor=1` (như `chup-anh-man-hinh-game`; script mẫu ở đó).
- Chuỗi nghi lệch cần có mặt trong ảnh (dữ liệu dài nhất, không phải mẫu đẹp).
- Chỗ cần xem, ghi toạ độ vùng để cắt phóng ×2.
- Đầu ra: đường dẫn ảnh; nhận xong đổi đuôi thư thành `.done.md`.
Khi có ảnh: mở bằng công cụ đọc ảnh, đo mép chữ và mép khung, đối chiếu số mức 1-2.

## Bước 4. Báo cáo
```
## Tóm tắt  (≤5 dòng: chỗ nào lệch/không, mức bằng chứng, còn vướng gì)
| Chỗ | Chuỗi | Rộng chữ | Rộng khung | Kết luận | Mức |
```
- Nêu giả định (font dự phòng, scale cha) để người sau kiểm lại.
- Chưa đạt mức 3: ghi "chưa thấy trên ảnh" và thêm ĐÚNG 1 dòng cuối `[CẦN SẾP] cần Tôm chạy: <lệnh một dòng>`.
- Sửa lệch: đề xuất `wordWrap`, hạ cỡ chữ, hoặc nới khung kèm con số, rồi nhờ chụp lại đúng lệnh cũ để có cặp trước/sau.

## Tiêu chí xong
- [ ] Mỗi chỗ nghi có chuỗi dài nhất và số đo (không chỉ "trông có vẻ").
- [ ] Ghi rõ mức bằng chứng 1/2/3; không nâng mức bằng lời.
- [ ] Lệnh nhờ Tôm chạy được nguyên văn, chỉ 1 dòng.
- [ ] Không chạy Playwright/lệnh khi chưa được phép.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| Đo bằng chuỗi ngắn, sau gặp tên dài bị tràn | lấy chuỗi dài nhất trong dữ liệu thật |
| Quên scale của container cha | nhân dồn scale mọi cấp trước khi so với khung |
| Số `measureText` nhỏ hơn ảnh thật | font chưa tải lúc đo, hoặc `resolution`/`stroke` làm rộng thêm |
| Kết luận "ổn" chỉ từ ước lượng | chỉ được ghi mức 1, kèm `[CẦN SẾP]` nếu quan trọng |
| Lệnh nhờ chụp bị chặn | có `X=2 python ...`/`export`: bỏ, chỉ gõ `python ...` |
