---
name: noi-giao-thuc-server-client-do-vat
description: Quy trình nối một tính năng đồ vật/tương tác (props, shop, thú cưng...) từ server sang client cho game CTFClanWar - chia việc giữa Tôm (shared + server) và Cua (client), chốt hợp đồng tin nhắn, rồi test hai đầu. Dùng khi Tôm xong server mà client chưa nối, hoặc khi thêm/đổi tin nhắn giao thức.
---
# Nối giao thức server → client cho đồ vật

Bài học từ đợt "đồ vật trên map có phản ứng": Tôm xong shared + server (13 test xanh) nhưng trong game chưa thấy gì vì client chưa nối. Kỹ năng này làm cho khoảng hở đó không bị bỏ quên.

## Mục tiêu
Một tính năng đồ vật chạy được từ đầu đến cuối: người chơi bấm/chạm → server kiểm → tin trả về → client vẽ/hiện đúng. Hai đầu đều có test, và không ai tự sửa phần của người kia.

## Phân chia
| Việc | Tôm | Cua |
|---|---|---|
| Kiểu tin + hằng số luật (tầm với, hồi chiêu, trần ngày) trong `shared/src` | ✔ viết | chỉ import, không chép số |
| Parser, kiểm vị trí/quyền, trần phần thưởng, lưu SQLite, giới hạn tốc độ (server) | ✔ | |
| Gửi lệnh (chạm, phím E), nhận tin trả, vẽ hiệu ứng, bảng UI (mua, thú cưng) | | ✔ |
| Xin tin đồng bộ khi vào/đổi khung nhìn (`propSync`-kiểu) | định nghĩa tin | gọi đúng lúc |
| Icon/art mới | báo thiếu | báo Kem/phòng art, không tự vẽ bừa |
Không sửa file của nhau; muốn nhờ thì gửi `inbox/` (RULES.md).

## Bước 1. Tôm chốt hợp đồng trước khi Cua bắt đầu
Trong báo cáo bàn giao (hoặc `shared/src/<tinh-nang>.ts`), liệt kê bảng:
| Tin | Hướng | Trường | Khi nào gửi | Lỗi có thể trả |
|---|---|---|---|---|
| `propAct {prop, act}` | client→server | id vật, tên hành động | người chơi bấm E/chạm | `propOk` kèm lý do từ chối |
| `propFx` | server→client | ... | chỉ người trong khung nhìn | không có |
Ghi rõ: giá trị đặc biệt (vd `id=0` nghĩa là "mình", `null` là không có hạng), tin nào là broadcast theo tầm nhìn, tin nào là trả riêng, thứ tự tin khi vào khu vực (sync trước hay fx trước). Tên trường lấy từ mã thật, không đoán.

## Bước 2. Tôm làm và kiểm đầu server
1. Kiểu + hằng số ở `shared`, parser từ chối đầu vào sai (âm, không nguyên, thiếu trường).
2. Server không tin client: dùng vị trí do server mô phỏng, kiểm tầm với, kiểm đang ở ngoài phố hay trong tiệm.
3. Chống spam nhiều lớp (giới hạn lệnh chung, giới hạn riêng, hồi chiêu theo vật).
4. Phần thưởng có trần ngày lưu DB, không cộng thẳng.
5. Mất kết nối/vào tiệm/bị dời xa: dọn trạng thái (tự đứng dậy...).
6. Commit riêng phần mình, chỉ các file của mình (kiểm `git status`, không kéo file người khác đang sửa dở).

## Bước 3. Bàn giao cho Cua bằng thư inbox
`inbox/<ngày>_tom_to_cua_<chủ-đề>.md` gồm: bảng hợp đồng (Bước 1), commit đã xong, cách chạy server thử, phần CHƯA có (vd nội thất chưa đồng bộ), icon còn mượn. Không gửi lời mơ hồ như "nối giúp".

## Bước 4. Cua nối client
- Gửi lệnh đúng trường; hiện từ chối của server (`propOk` lỗi) thành câu cho người chơi, không im lặng.
- Gọi lệnh đồng bộ khi vào khu vực/đổi khung nhìn, không chỉ lúc đăng nhập.
- Vẽ theo tin server, KHÔNG tự quyết kết quả (trúng/trượt, còn lượt) ở client.
- Xử lý giá trị rỗng (`null`, danh sách rỗng) không văng lỗi.
- Hiệu ứng lặp lại nhanh: chấp nhận server không phát lại trong thời gian hồi.

## Bước 5. Checklist test hai đầu
**Đầu server (Tôm)**
- [ ] Test đơn vị cho từng tin: hợp lệ, thiếu trường, sai kiểu, giá trị đặc biệt.
- [ ] Ngoài tầm với bị từ chối; trong tiệm bị từ chối.
- [ ] Spam: gửi vượt hạn mức → không phát hiệu ứng thêm, không cộng thưởng thêm.
- [ ] Trần ngày: lần thứ 2 trong ngày không thưởng; sang ngày mới thưởng lại.
- [ ] Tin chỉ tới người trong khung nhìn (một người xa + một người trong tiệm không nhận).
- [ ] Người mới đến nhận đủ trạng thái hiện có qua tin đồng bộ.
- [ ] Rớt mạng/dời xa → trạng thái được dọn.
- [ ] `npm run build` và `npm test`; test đỏ nào thì nói rõ có phải của mình không (đừng sửa file người khác đang dở).

**Đầu client (Cua)**
- [ ] Mỗi hành động gửi đúng tin, đúng trường (nhìn khung WS hoặc log).
- [ ] Mỗi tin trả về có xử lý: hiệu ứng, bảng UI, thông báo lỗi.
- [ ] Vào khu vực: trạng thái hiện có hiện đúng (người đang ngồi, mèo đi theo...).
- [ ] Giá trị rỗng/`null` không gây lỗi console.
- [ ] Lỗi từ chối hiển thị cho người chơi.
- [ ] Chạy kèm kiểm khói (`choi-thu-headless-kiem-man-nap-ngay-dem-nha-rieng`) và chụp màn hình (`chup-anh-man-hinh-game`): console 0 lỗi.

**Hai đầu cùng lúc (làm sau khi cả hai xong)**
- [ ] Hai tài khoản mới (tên `smoke_<epoch>`): A làm hành động, B ở gần thấy hiệu ứng, C ở xa không thấy.
- [ ] A đi xa rồi quay lại: B/C vào khung nhìn thì nhận đồng bộ đúng.
- [ ] Làm đủ chuỗi trần ngày một lần, xem phần thưởng vào túi/HC đúng số.
- [ ] Ghi kết quả thật; chưa chạy thì ghi "chưa chạy", không suy đoán.

## Tiêu chí xong
- [ ] Bảng hợp đồng tin nằm trong báo cáo và khớp mã `shared`.
- [ ] Phía server và phía client đều có test/kiểm đã chạy, kết quả ghi rõ.
- [ ] Danh sách "còn thiếu" nêu rõ (art, khu vực chưa đồng bộ) và có chủ.
- [ ] Không file nào bị sửa ngoài phần của mình.

## Lỗi hay gặp
| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Server xanh mà game không thấy gì | client chưa nối; bàn giao qua inbox ở Bước 3 |
| Client chép số luật (tầm với, hồi chiêu) lệch server | phải import từ `shared` |
| Người vào sau không thấy trạng thái | thiếu lệnh đồng bộ khi vào khu vực |
| Client `null` làm văng lỗi | hợp đồng không nêu giá trị rỗng; thêm vào bảng Bước 1 |
| Kiểu `shared` đổi mà chưa ghi chú ý nghĩa mới | cập nhật chú thích + báo Cua |
| Test đỏ ở file không phải của mình | báo rõ, không sửa file người đang làm dở |
| Phần thưởng cộng nhiều lần | thiếu trần ngày lưu DB, kiểm lại Bước 2.4 |
