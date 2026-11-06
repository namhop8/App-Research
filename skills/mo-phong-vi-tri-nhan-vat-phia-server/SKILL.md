---
name: mo-phong-vi-tri-nhan-vat-phia-server
description: Mô phỏng vị trí nhân vật phía server trong phó bản CTFClanWar (trượt khi tàu nghiêng, đứng ngoài vùng an toàn) để server tự kiểm và sát thương/khoá theo vị trí của mình, không tin vị trí client gửi. Dùng khi Tôm thêm hoặc sửa cơ chế có vị trí (nghiêng, trượt, vùng thu hẹp) trong phó bản.
---
# Mô phỏng vị trí nhân vật phía server (trượt, vùng an toàn)

Nguyên tắc: **vị trí là của server**. Client chỉ gửi *ý định* (hướng/phím), server tự tính vị trí, trượt, kiểm vùng. Client dự đoán và nội suy để mượt, khi lệch thì kéo về theo server.

## Mục tiêu
Mỗi tick server biết chính xác ai đang ở đâu, có trượt không, có trong vùng an toàn không, từ đó tính sát thương/phạt. Chạy lại cùng đầu vào cho cùng kết quả (xác định), kiểm được bằng test không cần mở game.

## Bước 0. Đọc trước, đừng đoán
1. `DESIGN_DUNGEON` mục cấp đang làm: góc nghiêng, lúc nào nghiêng, vùng an toàn thu từ vòng nào, sát thương/giây.
2. Mã di chuyển hiện có của server (tốc độ, kích thước ô, va chạm) và `shared/src` phần `dg*`. Dùng ĐÚNG tên thật; số luật nằm ở `shared`, client chỉ import.
3. Thiết kế mâu thuẫn (vd vùng thu vòng 4 hay vòng 5): ghi báo cáo, theo mục riêng của cấp, hỏi sếp/Tôm chốt.

## Bước 1. Bảng hằng số (đặt ở `shared`, Tôm chốt)
| Hằng | Ý nghĩa | Đơn vị |
|---|---|---|
| `TICK_MS` | bước mô phỏng cố định | ms |
| `MAX_SPEED` | tốc độ đi tối đa của nhân vật | px/s |
| `SLIDE_ACCEL` | gia tốc trượt theo hướng nghiêng | px/s² |
| `SLIDE_MAX` | vận tốc trượt tối đa | px/s |
| `FRICTION` | giảm vận tốc trượt khi bám/đứng yên | 1/s |
| `SAFE_*` | tâm, bán kính (hoặc hình chữ nhật) vùng an toàn theo vòng | px |
| `OUT_GRACE_MS` | ân hạn trước khi tính "ngoài vùng" | ms |
| `OUT_DPS` / `OUT_TICK_COST` | phạt mỗi giây/tick ngoài vùng | tuỳ luật |
| `POS_TOLERANCE` | sai lệch tối đa chấp nhận so với client báo | px |
Không gõ số trực tiếp trong logic; mọi số đọc từ bảng này.

## Bước 2. Vòng mô phỏng (mẫu)
Bước cố định, không dùng `dt` thật của máy để tránh kết quả đổi theo độ trễ:
```ts
// mỗi TICK_MS, cho từng người trong trận
const dt = TICK_MS / 1000;
const want = clampDir(p.input);                 // hướng ý định, độ dài <= 1, đã kiểm ở parser
let vx = want.x * MAX_SPEED, vy = want.y * MAX_SPEED;

if (ship.tilt.active) {                         // tàu nghiêng: cộng vận tốc trượt
  p.slide.x += ship.tilt.dir.x * SLIDE_ACCEL * dt;
  p.slide.y += ship.tilt.dir.y * SLIDE_ACCEL * dt;
  p.slide = limit(p.slide, SLIDE_MAX);
} else {
  p.slide = scale(p.slide, Math.max(0, 1 - FRICTION * dt));
}
const next = add(p.pos, scale(add({x:vx,y:vy}, p.slide), dt));
p.pos = collide(next, map);                     // va chạm tường/mép tàu của server
```
Điểm cần giữ:
- Trượt cộng vào vị trí **sau** ý định, và vẫn bị va chạm chặn (không trượt xuyên tường, không rơi khỏi map).
- Nghiêng có pha: báo trước (`tilt.warnMs`) → nghiêng → hồi. Ba pha đều do server giữ giờ.
- Người đang bị khoá/chết/hồi sinh: ngừng nhận ý định, vẫn có thể bị trượt hay không phải ghi rõ trong luật.

## Bước 3. Vùng an toàn và đứng ngoài
```ts
const inside = inSafe(p.pos, safeZone(round));  // vùng theo vòng, từ shared
if (inside) { p.outMs = 0; }
else { p.outMs += TICK_MS; if (p.outMs > OUT_GRACE_MS) applyPenalty(p, dt); }
```
- Vùng thu hẹp: vị trí vùng nội suy theo thời gian server, không nhảy cục (nếu luật là nhảy thì báo trước bằng tin).
- Phạt chỉ cộng ở server; kết quả đi qua tin (HP/điểm/khoá), client không tự trừ.
- Biên: đứng đúng mép tính là trong; ghi quy ước và test cả hai phía.

## Bước 4. Nhận vị trí từ client (nếu có)
Ưu tiên **chỉ nhận ý định**. Nếu game cần client báo vị trí để mượt:
1. Parser từ chối thiếu trường, NaN, không hữu hạn, ngoài map.
2. Quãng đường từ vị trí hợp lệ trước tới vị trí báo ≤ `(MAX_SPEED + SLIDE_MAX) * Δt + POS_TOLERANCE`, với `Δt` là thời gian server đo, không tin dấu giờ client.
3. Vượt ngưỡng: **bỏ vị trí client, giữ vị trí server**, gửi tin sửa vị trí (snap) cho riêng người đó; đếm vi phạm, quá hạn mức thì cảnh báo/ngắt (theo quy chế game, hỏi Tôm).
4. Giới hạn tần số tin vị trí, chống spam.

## Bước 5. Đồng bộ cho client
- Tin vị trí kèm số thứ tự lệnh đã xử lý để client dự đoán lại (reconciliation) và nội suy người khác.
- Tin trạng thái nghiêng/vùng: có giá trị rỗng (`null` khi không nghiêng), đơn vị giây hay ms ghi rõ; người vào muộn nhận đồng bộ đầy đủ trước (theo `noi-giao-thuc-server-client-do-vat` Bước 1).
- Client chép số luật = lỗi; phải import từ `shared`.

## Bước 6. Test (không cần mở game)
Viết test chạy vòng mô phỏng với đầu vào cố định:
- [ ] Đứng yên khi nghiêng: sau N tick vị trí đúng công thức, không vượt `SLIDE_MAX`.
- [ ] Trượt vào tường: dừng ở tường, không xuyên, không ra ngoài map.
- [ ] Hết nghiêng: vận tốc trượt tắt dần theo `FRICTION`.
- [ ] Ngoài vùng ít hơn `OUT_GRACE_MS` → không phạt; vượt → phạt đúng số theo tick; quay vào → `outMs` về 0.
- [ ] Vùng thu hẹp ở vòng mới: người đang đứng giữa mép bị tính đúng.
- [ ] Client báo vị trí dịch chuyển tức thời / tốc độ gấp 10 → bị từ chối, vị trí server không đổi.
- [ ] Tick chạy trễ (gộp nhiều tick): kết quả bằng chạy từng tick.
- [ ] Hai lần chạy cùng đầu vào cho cùng kết quả.
- [ ] Rớt mạng/vào muộn: trạng thái trượt và `outMs` được dọn hoặc đồng bộ đúng.
Rồi `npm run build` và `npm test`; test đỏ ở file người khác thì báo rõ, không sửa. Playtest theo `dung-man-pho-ban-theo-tang` Bước 5 (có chế độ rút ngắn).

## Tiêu chí xong
- [ ] Bảng hằng số ở `shared`, logic không số gõ tay.
- [ ] Vị trí, trượt, vùng, phạt đều tính ở server; client chỉ gửi ý định hoặc vị trí đã được kiểm.
- [ ] Mọi mục Bước 6 có test, kết quả ghi thật (chưa chạy thì ghi "chưa chạy").
- [ ] Hợp đồng tin (Bước 5) đã gửi Cua qua `inbox/`.
- [ ] Chỗ thiết kế mâu thuẫn được ghi và có người chốt.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| Kết quả đổi theo máy/độ trễ | dùng bước cố định `TICK_MS`, không dùng `dt` thật |
| Người chơi bị kéo giật liên tục | `POS_TOLERANCE` quá chặt hoặc bỏ sót `SLIDE_MAX` trong ngưỡng |
| Trượt xuyên tường | va chạm áp sau khi cộng trượt, kiểm cả vận tốc trượt |
| Phạt cộng hai lần một tick | chỉ một chỗ áp phạt; test đếm số lần |
| Hai đầu lệch cách tính vùng | client import cùng hàm `inSafe` từ `shared` |
| Đứng đúng mép khi vùng thu, lúc bị lúc không | chốt quy ước biên, test hai phía |
| Thiếu quyền chạy lệnh/ghi file | hỏi sếp 1 lần bằng `[CẦN SẾP]`, nêu rõ lệnh; không hỏi lại |
