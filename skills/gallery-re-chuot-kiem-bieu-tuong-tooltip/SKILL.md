---
name: gallery-re-chuot-kiem-bieu-tuong-tooltip
description: Thêm vào ui_gallery (CTFClanWar, tools/playtest/ui_gallery.mjs) bước tự rê chuột lên một ô khoá của mỗi bảng, chụp tooltip và kiểm "ô không còn câu trạng thái". Dùng khi soát luật Biểu tượng + rê chuột (statusIcon/bindTip) bằng máy thay vì mắt, gồm cách nối bước này vào vòng chạy bảng cho cả Phó bản và Tháp.
---
# Gallery: rê chuột ô khoá, chụp tooltip, kiểm ô hết câu trạng thái

## Mục tiêu
Luật: ô chỉ có **biểu tượng** trạng thái (khoá, đạt, đang làm, hết hàng...), chữ trạng thái nằm trong **tooltip** khi rê chuột/chạm giữ. Mỗi bảng trong gallery tự: (a) tìm một ô khoá, (b) rê chuột lên, (c) chụp tooltip, (d) kiểm ô không còn câu trạng thái và tooltip đủ nội dung. Kết quả vào trang HTML gallery, cùng cột với lỗi chữ/tương phản/bố cục.

## Cần biết trước (đọc mã, không đoán)
- Helper: `client/src/ui/statusTip.ts` (`statusIcon`, `bindTip`, `statusTipLines`; `kind`: lock, done, ready, busy, soldout, warn, online, offline). Tooltip vẽ bằng `Tooltip` trong `overlays.ts`.
- Danh sách chỗ còn câu trạng thái: `docs/UI_STATUS_ICON_AUDIT.md` (lấy cụm từ cần cấm).
- `tools/playtest/ui_gallery.mjs`: mỗi bảng có hàm mở + chụp; chạy `npm run ui-gallery -- --ports <cổng> [--only <tên>] [--no-build]`. Chọn cổng riêng của mình, không dùng cổng người khác.
- Kỹ năng này CHƯA kiểm trên mã thật: mở file, xác nhận tên hàm/biến trước khi dán; lệch thì sửa theo mã.

## Bước 1. Cho gallery tìm được ô khoá (đừng dò bằng mắt/toạ độ cứng)
Trong `statusIcon`/`bindTip`, khi `?debug=1`, ghi vào sổ chung:
```ts
// statusTip.ts (chỉ khi debug) - mỗi biểu tượng đăng ký 1 dòng
const reg = ((window as any).__statusIcons ??= []) as any[];
reg.push({ kind, obj, cell: tooltipTarget /* ô chứa */, title: opts.title });
// khi obj bị huỷ: obj.once('destroy', () => reg.splice(reg.indexOf(entry), 1));
```
Trong gallery lấy ra toạ độ màn hình (đã nhân scale canvas và offset trang):
```js
const info = await page.evaluate(() => {
  const g = window.game, cv = g.canvas, r = cv.getBoundingClientRect();
  const sx = r.width / g.scale.width, sy = r.height / g.scale.height;
  const e = (window.__statusIcons || []).find(i => i.kind === 'lock' && i.obj.active && i.obj.visible);
  if (!e) return null;
  const b = e.cell.getBounds();                       // ô, không chỉ icon
  return { x: r.left + (b.centerX) * sx, y: r.top + (b.centerY) * sy,
           rect: { x: b.x, y: b.y, w: b.width, h: b.height }, title: e.title };
});
```
Không có ô khoá: thử `soldout` rồi `busy`; bảng không có biểu tượng nào ghi "không có ô khoá", đừng coi là lỗi.

## Bước 2. Trước khi rê: lấy chữ trong ô
Dùng đúng bộ đo chữ của gallery (`auditText`) hoặc quét Text Phaser nằm trong `rect`:
```js
const before = await page.evaluate(r => game.scene.getScenes(true).flatMap(s => s.children.list)
  .filter(o => o.type === 'Text' && o.visible && o.text.trim()).filter(o => {
    const b = o.getBounds(); return b.centerX > r.x && b.centerX < r.x + r.w && b.centerY > r.y && b.centerY < r.y + r.h; })
  .map(o => o.text), info.rect);
```
Chữ DOM (nếu bảng dùng HTML) quét thêm bằng `elementsFromPoint` trong vùng ô.

## Bước 3. Rê chuột, chụp tooltip
```js
await page.mouse.move(info.x - 30, info.y - 30);    // đưa chuột ra ngoài trước, để sinh pointerover thật
await page.mouse.move(info.x, info.y, { steps: 6 });
await page.waitForTimeout(250);                      // tooltip hiện ngay với chuột; chờ 1-2 khung
const tip = await page.evaluate(() => game.scene.getScenes(true).flatMap(s => s.children.list)
  .filter(o => o.name === 'statusTip' || o.getData?.('tooltip')).map(o => o.getBounds()));
```
Nếu `Tooltip` chưa đặt `name`/dữ liệu nhận diện, thêm `setName('statusTip')` (một dòng) thay vì dò theo màu. Chụp: `page.screenshot({ path, clip })` với `clip` = hợp của ô và tooltip, đệm 16 px, cắt trong khung canvas; thêm ảnh cả bảng để sếp thấy ngữ cảnh. Sau khi chụp: `mouse.move(0, 0)` và kiểm tooltip đã biến mất.

## Bước 4. Các phép kiểm (đỏ nếu sai)
| # | Kiểm | Đạt khi |
|---|---|---|
| 1 | Ô không còn câu trạng thái | `before` không chứa cụm trong danh sách cấm (ví dụ: "Đã khoá", "Chưa mở", "Hết hàng", "Đang làm", "Sẵn sàng", "Cần cấp", "Đạt"). Lấy cụm từ `UI_STATUS_ICON_AUDIT.md`; so không phân biệt hoa thường, bỏ dấu |
| 2 | Tooltip hiện khi rê | có đối tượng tooltip `visible`, bounds nằm trong canvas |
| 3 | Tooltip đủ dòng | chứa tên ô (`title`) và tên trạng thái; dùng `statusTipLines` làm chuẩn |
| 4 | Tooltip không tràn/đè | bounds nằm trọn trong 1280×720; chạy cùng bộ soát chữ/tương phản lên tooltip |
| 5 | Tooltip gỡ khi rời | sau `mouse.move(0,0)` không còn tooltip |
| 6 | Không lỗi console | 0 `pageerror` trong bước rê |
Nội dung kiểm 1 là **chữ nằm trong ô**; chữ tên vật phẩm, giá, số lượng vẫn được phép. Danh sách cấm chỉ gồm câu trạng thái, đừng cấm cả chữ thường.

## Bước 5. Ghi vào trang HTML gallery
Mỗi bảng thêm: ảnh tooltip, `kind` đã rê, kết quả 6 phép kiểm (xanh/đỏ), danh sách chữ còn trong ô. Bảng không có biểu tượng: dòng "không có ô khoá". Bảng chưa chuyển sang biểu tượng (nhiều bảng chưa đổi): ghi "chưa áp luật" và đếm riêng, KHÔNG làm đỏ cả lượt; chỉ đỏ ở bảng đã khai báo đã chuyển (cờ trong bảng cấu hình gallery).
Kết thúc lượt in tổng: `N bảng có ô khoá / M đạt / K đỏ / L chưa áp luật`.

## Bước 5b. Nối vào `ui_gallery.mjs` (gồm Phó bản và Tháp)
Mô tả ở trên chưa chạy được nếu chưa nối. Làm theo thứ tự, mỗi mục xong thì chạy `--only` một bảng:
1. **Một hàm dùng chung** `hoverLockProbe(page, panelName, cfg)` trong `ui_gallery.mjs`: gom Bước 1-4, trả về `{ verdict, kind, tipShot, remainingTexts, checks[6] }`. Không chép lại cho từng bảng.
2. **Gọi sau khi bảng đã mở và chụp ảnh thường** (đừng đổi ảnh gốc), trước lệnh đóng bảng. Bọc `try/catch`: lỗi của probe chỉ ghi vào mục của bảng đó, không làm gãy cả lượt.
3. **Cờ trong bảng cấu hình**: mỗi bảng thêm `statusIconApplied: true|false` (mặc định false = "chưa áp luật") và tuỳ chọn `lockKinds` (thứ tự thử, mặc định `['lock','soldout','busy']`).
4. **Phó bản**: các bảng phó bản mở bằng móc debug/`closeEverything` như `dung-man-pho-ban-theo-tang`. Cần dựng trạng thái có ô khoá (ví dụ trạm chưa mở, cấp cao hơn người chơi) bằng dữ liệu giả trong gallery, không chờ chơi thật. Trạm/vòng khoá nằm trong HUD hay bảng nào thì probe chạy trong bảng đó.
5. **Tháp**: bảng cửa tháp / bậc / chứng chỉ khoá (xem `kiem-client-man-thi-giay-chung-nhan-playwright`). Dùng dữ liệu giả thiếu chứng chỉ để chắc chắn có ô khoá; ô khoá cửa có thể là DOM chứ không phải Phaser, nên `cell` có thể là phần tử, tính toạ độ bằng `getBoundingClientRect`.
6. **Tổng kết**: cộng vào bảng tổng đầu trang HTML và in dòng `N bảng có ô khoá / M đạt / K đỏ / L chưa áp luật` cuối lượt. Phó bản và Tháp đếm riêng thành 2 dòng con để Mực thấy hai khu này đã phủ chưa.
7. **Thêm cờ dòng lệnh** `--no-hover` (tắt probe khi cần chạy nhanh); mặc định bật.

Nếu mã thật không giống các tên ở trên (chưa kiểm, xem "Cần biết trước"), sửa tên theo mã rồi ghi chỗ lệch vào báo cáo.

## Bước 6. Chạy
```
npm run ui-gallery -- --ports 5900 --only "<tên bảng>"
```
Chạy một bảng trước, mở ảnh xem thật, rồi mới chạy cả 55 bảng. Lệnh trần, không `export`/`X=2 npm ...`.

## Tiêu chí xong
- [ ] `hoverLockProbe` đã được gọi từ vòng chạy bảng; có ít nhất 1 bảng Phó bản và 1 bảng Tháp ra kết luận (đạt/đỏ), không chỉ "chưa áp luật".
- [ ] Mỗi bảng có kết luận một trong: đạt / đỏ (kèm phép kiểm sai) / không có ô khoá / chưa áp luật.
- [ ] Đã tự mở ít nhất 3 ảnh tooltip để nhìn thật (không chỉ tin cờ xanh).
- [ ] Số bảng mở và lỗi console không tệ hơn mốc trước (ghi mốc: 55/55 mở).
- [ ] Bước rê không làm đổi trạng thái bảng kế tiếp (đã `mouse.move(0,0)`, đóng bảng như `closeEverything`).
- [ ] Không bấm vào ô, chỉ rê (rê không được gây mua/mở).

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| Tooltip không hiện dù rê | chuột chưa qua `pointerover` thật: đi từ ngoài vào bằng `steps`; ô bị lớp khác che (kiểm `elementsFromPoint`/`input.hitTestPointer`) |
| Toạ độ lệch | quên nhân scale canvas hoặc offset trang; dùng `getBoundingClientRect` như Bước 1 |
| Tìm thấy icon của bảng khác | sổ `__statusIcons` còn mục cũ: dọn khi `destroy`, lọc `obj.active && visible` và nằm trong bảng đang mở |
| Báo "còn câu trạng thái" nhầm | cụm cấm trùng tên vật phẩm; thu hẹp cụm hoặc so theo cả câu |
| Tooltip bị chụp lẫn của ô trước | `mouse.move(0,0)` + chờ 1 khung giữa các bảng |
| Lượt chạy đỏ vì cây làm việc dở của người khác | thêm `--no-build`; ghi rõ lỗi không thuộc phần mình |
| Probe làm gãy bảng sau | thiếu `try/catch` hoặc quên `mouse.move(0,0)`; probe phải tự dọn trước khi đóng bảng |
| Phó bản/Tháp không có ô khoá khi mở bằng dữ liệu mặc định | dựng dữ liệu giả có khoá (Bước 5b mục 4-5), đừng kết luận "không có ô khoá" vội |
| Chạm giữ 450 ms (cảm ứng) | gallery chỉ soát chuột; chạm giữ đã có test đơn vị ở `statusTip` |
| Thiếu quyền chạy lệnh/ghi `tools/playtest/` | hỏi sếp ĐÚNG 1 lần bằng `[CẦN SẾP]` |
