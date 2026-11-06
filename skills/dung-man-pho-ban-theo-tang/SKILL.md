---
name: dung-man-pho-ban-theo-tang
description: Dựng màn phó bản cấp N (cấp 3, 4...) cho game CTFClanWar từ khung của cấp trước - chia checklist nối tin `dg*`, khoá trạm, đồng hồ HUD, rồi playtest `--tier N` kèm chế độ rút ngắn. Dùng khi bắt đầu một cấp phó bản mới hoặc sửa cơ chế một cấp đã có.
---
# Dựng màn phó bản theo tầng (cấp N) từ khung có sẵn

Cấp 1-2 đã có khung (màn, nối tin `dg*`, khoá trạm kiểu `tripped`, playtest `--tier N`). Cấp N+1 **dùng lại khung, chỉ thêm phần khác biệt**. Không viết màn mới từ đầu.

## Mục tiêu
Một cấp mới chơi được từ đầu đến cuối: vào phó bản → các vòng/trạm → boss → kết thúc. Server là đồng hồ và luật chính; client chỉ vẽ theo tin. Có playtest `--tier N` chạy đầy đủ và chạy rút ngắn.

## Bước 0. Đọc trước, đừng đoán
1. `DESIGN_DUNGEON` (mục cấp N, bảng thông số vòng/đề/thời gian, mục playtest). Chép bảng "cấp N khác cấp N-1 ở đâu" ra báo cáo.
2. Mã cấp trước (vd `dungeonTier2.ts`, `dungeonLive.ts`) và `shared/src` phần `dg*`: dùng ĐÚNG tên thật, không đặt tên mới trong `shared/`.
3. Chỗ thiết kế tự mâu thuẫn (vd bảng chung nói vùng an toàn thu từ vòng 4, mục cấp N nói vòng 5): ghi vào báo cáo, theo mục riêng của cấp N, và hỏi sếp/Tôm chốt. Không tự chọn lặng lẽ.
4. Bản đồ Tiled + asset cấp N đã có chưa? Thiếu thì báo phòng art (Kem), không tự vẽ.

## Bước 1. Bảng khác biệt (làm trước khi code)
| Mục | Cấp N-1 | Cấp N | Dùng lại / làm mới | Chủ |
|---|---|---|---|---|
Mỗi hàng là một cơ chế: số vòng, thời gian vòng, số trạm, tốc độ lính, phạt nộp sai, boss (đòn, phase), vùng an toàn, đồng hồ, trạm phụ. Cơ chế nào đã có ở khung thì ghi "dùng lại" + tên cờ/tin hiện có.

## Bước 2. Hợp đồng tin `dg*` (Tôm chốt, Cua chờ)
Theo `noi-giao-thuc-server-client-do-vat` Bước 1. Cho cấp N, bảng phải nêu cho từng cơ chế mới:
- tên tin, hướng, trường, đơn vị (giây hay ms), giá trị rỗng/`null`;
- tin nào là broadcast theo clan, tin nào trả riêng;
- thứ tự khi vào giữa trận (đồng bộ trạng thái đầy đủ trước, tin tăng dần sau);
- cơ chế cần cả vị trí (vd tàu nghiêng, trượt): vị trí là của server, client chỉ dự đoán/vẽ.
Chưa có hợp đồng thì Cua có thể khai kiểu tạm trong `client/` và ghi "cần đưa vào shared", KHÔNG sửa `shared/`.

## Bước 3. Khoá trạm
Dùng lại một cờ trạng thái cho mọi kiểu khoá (`tripped`, `locked`...), đừng mỗi cơ chế một cờ:
- Mỗi nguồn khoá có: ai khoá, khoá đến khi nào (hết giờ hay giải đề), ai mở được.
- Client: trạm khoá vẽ khác (biểu tượng + chữ lý do), bấm vào hiện câu giải thích, không im lặng.
- Hai nguồn khoá cùng lúc: kết quả theo server; test cả hai.
- Hết khoá/giải xong → tin mở khoá tới đủ người trong trận, kể cả người vào muộn.

## Bước 4. Đồng hồ và cảnh báo HUD
Mỗi đồng hồ mới (tiền chuộc, vòng, hồi nộp...) cần đủ 4 thứ:
1. Hiển thị `mm:ss` lấy từ **giây còn lại server gửi**; client chỉ đếm xuôi giữa hai tin để mượt, rồi hiệu chỉnh theo tin mới.
2. Đổi tốc độ (vd boss làm nhanh gấp đôi): đọc từ tin, không gõ hằng số ở client.
3. Cảnh báo sắp hết (ngưỡng đọc từ `shared`), và thông báo khi hết/mất đồ.
4. Reconnect/vào muộn: đồng hồ hiện đúng ngay, không về 0 hay nhảy.
Các HUD nằm ngoài canvas hay trong scene thì theo khung cấp trước; kiểm bằng `chup-anh-man-hinh-game` + `kiem-lech-giao-dien-canvas-khong-playwright`.

## Bước 5. Playtest `--tier N` và chế độ rút ngắn
Playtest thật cấp N dài (vd 7 vòng × 4 phút ≈ 30+ phút). Cần hai chế độ, ghi rõ trong báo cáo cái nào đã chạy:
| Chế độ | Dùng khi | Ghi chú |
|---|---|---|
| Đầy đủ `--tier N` | nghiệm thu trước khi sếp ký | giờ thật, ghi tổng thời gian |
| Rút ngắn (`--demo`, hoặc lệnh bỏ vòng `phoban skip`) | kiểm nhanh từng cơ chế | CHỈ bật khi server chạy dev/test, bị tắt ở bản thật |
Mẫu lệnh (tên cờ lấy từ script thật, đọc `--help`/mã trước): `node dungeon.mjs --tier N`, `node dungeon.mjs --tier N --demo`.
Chế độ rút ngắn phải: co thời gian vòng/hồi nhưng giữ nguyên thứ tự và luật; vẫn đi qua mỗi cơ chế mới ít nhất một lần (khoá trạm, đồng hồ hết giờ, boss mỗi đòn/phase). Không bao giờ coi kết quả rút ngắn là nghiệm thu cuối.
Chạy tuần tự cấp thấp trước: cấp N-1 xanh rồi mới `--tier N`, để biết hồi quy hay lỗi mới. Tên tài khoản mới mỗi lượt (`smoke_<epoch>`), tắt server nền khi xong. Lệnh gõ trần, không `export`/`X=2 python`.

## Bước 6. Kiểm chéo cấp cũ
Sau khi thêm cấp N chạy lại `--tier 1` và `--tier 2` (hoặc N-1): khung chung bị sửa dễ làm hỏng cấp cũ. Ghi kết quả từng cấp.

## Tiêu chí xong
- [ ] Bảng khác biệt cấp N (Bước 1) và chỗ thiết kế mâu thuẫn được ghi rõ, có người chốt.
- [ ] Hợp đồng `dg*` khớp mã `shared`; client không chép số luật.
- [ ] Khoá trạm: mọi nguồn khoá có test + hiển thị lý do.
- [ ] Mỗi đồng hồ qua đủ 4 ý Bước 4, có ảnh HUD đã nhìn.
- [ ] `--tier N` rút ngắn chạy xanh; đầy đủ chạy xanh hoặc ghi "chưa chạy, cần ~X phút".
- [ ] `--tier` cấp cũ vẫn xanh; console 0 lỗi.
- [ ] Danh sách còn thiếu (art, bản đồ, quyết định) có chủ.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| Client chạy trước khi Tôm chốt `dg*` | dừng, khai kiểu tạm, gửi inbox cho Tôm; đừng đặt tên trong `shared/` |
| Đồng hồ nhảy khi vào muộn | thiếu tin đồng bộ đầy đủ; client đừng tự giữ giờ gốc |
| Cấp cũ hỏng sau khi sửa khung | chạy Bước 6; tách phần riêng cấp N khỏi khung |
| Chế độ rút ngắn lọt vào bản thật | chỉ bật qua cờ dev; kiểm bản build |
| Playtest đầy đủ quá lâu, hết quota | chạy nền, giới hạn 2 thread, chia theo vòng; không lặp quá 3 lần rồi hỏi sếp |
| Cơ chế cần vị trí (nghiêng, trượt) lệch giữa hai đầu | vị trí do server mô phỏng; client chỉ nội suy; xem `mo-phong-vi-tri-nhan-vat-phia-server` |
| Thiếu quyền chạy lệnh/ghi file | hỏi sếp 1 lần bằng `[CẦN SẾP]`, nêu rõ lệnh; không hỏi lại |
