---
name: do-loi-koth-ad-tren-trinh-duyet
description: Dò lỗi chế độ KOTH (chiếm đồi) và A-D (tấn công/phòng thủ) của game web bằng trình duyệt thật - dựng trận bằng bot, cho người dùng trình duyệt đi vào trụ sở và bấm phím E thật, đọc chữ trên các bảng (DOM hoặc Phaser) rồi so trước/sau mỗi tick. Dùng khi sửa luật chiếm/điểm/bảng điểm trận và cần bằng chứng chạy thật, không chỉ test server.
---
# Dò lỗi KOTH / A-D trên trình duyệt

## Mục tiêu
Bắt lỗi mà test server không thấy: bảng hiện sai số, phím E không kích hoạt, client lệch server sau tick. Cách làm: bot tạo tình huống, **một** người dùng trình duyệt chơi thật, script chụp "trước/sau" mỗi tick rồi so với số của server. Đây là kiểm tra hành vi, không thay test luật thuần ở server.

Nền chung (cài Playwright, server tĩnh, swiftshader, tài khoản mới, đóng server): xem `chup-anh-man-hinh-game` Bước 0-3b và `choi-thu-headless-kiem-man-nap-ngay-dem-nha-rieng`. Móc `__state`/`__debug` dưới `?debug=1`: xem Bước 1 của kỹ năng sau. Không nhắc lại.

## Ai chạy
Phòng bị cấm chạy Playwright/bot: chỉ viết `tools/koth_ad_probe.py` + lệnh chạy, thêm ĐÚNG 1 dòng `[CẦN SẾP] cần quyền chạy python tools/koth_ad_probe.py (Playwright + bot, localhost)`. Chưa có `probe.json` thì không tự suy kết quả.

## Bước 0. Đọc mã trước (không đoán tên)
- Server: luật trận (bán kính vùng chiếm, điểm/tick, thời gian chiếm, đội thắng), `TICK_MS`, tin nhắn trạng thái trận gửi client.
- Client: nơi xử lý phím **E** (tìm `KeyCodes.E` / `keydown` / `"KeyE"`), điều kiện gần trụ sở (khoảng cách, đúng đội), và **bảng chữ** hiện điểm, chủ đồi, đội hình, đếm ngược.
- Bot: có sẵn không (`tools/`, `server/bots`)? Cách bật, cách gán đội, cách cho đứng yên/đi tới đồi. Chưa có thì nhờ phòng dev thêm lệnh dưới `?debug=1`/cờ server, đừng tự sửa server.

## Bước 1. Dựng trận bằng bot
1. Khởi server dev trên cổng trống, tắt giới hạn ngoài (đợi người đủ) nếu có cờ test.
2. Tạo phòng/trận, thêm bot cho **cả hai đội** theo kịch bản cố định (seed cố định), vd:
   - K1: bot địch đứng ngoài vùng; người dùng vào vùng -> đội ta chiếm.
   - K2: bot địch vào vùng cùng lúc -> tranh chấp (không ai cộng điểm).
   - K3: bot địch ở trong, người dùng vào rồi ra -> trả lại chủ cũ.
   - A-D: bot tấn công một dịch vụ/mục tiêu, bot phòng thủ vá; kiểm điểm tấn/thủ và đổi pha.
3. Người dùng trình duyệt dùng tên mới `koth_<epoch>`; bot đặt tên có tiền tố `bot_`. Không đụng dữ liệu thật.

## Bước 2. Vào trụ sở bằng phím E THẬT
Không gọi hàm nội bộ thay cho phím; hàm nội bộ chỉ để đặt vị trí xuất phát nếu quá xa.
```python
pg.evaluate("__debug.teleport(x, y)")        # tên theo mã; chỉ để tới gần cửa
pg.wait_for_timeout(300)
pg.keyboard.down("KeyW")                      # hoặc đi thật tới cửa nếu gần
pg.wait_for_timeout(500); pg.keyboard.up("KeyW")
pg.keyboard.press("e")                        # phím thật, có keydown + keyup
pg.wait_for_function("__state().scene !== prev_scene || __state().inHq", timeout=5000)
```
Quy tắc: canvas phải có tiêu điểm (`pg.click("canvas")` trước, hoặc `pg.focus`); giữ phím >= 1 khung hình nếu game đọc theo `update` (`down` -> chờ 80-120ms -> `up`) thay vì `press` chớp. Kiểm cả ca **âm**: đứng xa cửa bấm E -> không vào; sai đội -> bị từ chối (có thông báo).

## Bước 3. Đọc chữ trên bảng: DOM hay Phaser?
Xác định trước, mỗi bảng một lần:
```python
dom = pg.evaluate("document.body.innerText.trim().length")   # > 0 => có chữ DOM
```
- **Chữ DOM** (div/overlay): `pg.locator("#scoreboard").inner_text()` hoặc `get_by_text`. Đọc được cả khi canvas không chụp ảnh.
- **Chữ Phaser** (`Text`/`BitmapText` trong scene): không có trong DOM. Đọc qua scene:
```python
TEXTS = """() => {
  const out = [];
  const walk = (o) => { if (o.text !== undefined && o.visible !== false && o.active !== false)
        out.push({k: o.name || o.constructor.name, t: String(o.text), x: Math.round(o.x), y: Math.round(o.y)});
      (o.list || []).forEach(walk); };
  game.scene.getScenes(true).forEach(s => s.children.list.forEach(walk));
  return out; }"""
rows = pg.evaluate(TEXTS)
```
  Biến `game` đặt theo mã (`window.game`/`__debug.game`); chưa lộ ra thì nhờ phòng dev lộ dưới `?debug=1`. Lọc theo `name`/vùng toạ độ để lấy đúng bảng; chữ trong `Container` đã được `walk` đệ quy. Chữ trên bảng vẽ thẳng vào canvas (texture) thì không đọc được: chụp ảnh và nhìn, hoặc nhờ dev đặt `__state().board`.
- Luôn lấy **nguồn thật** song song: `__state()` hoặc tin nhắn trạng thái (`pg.on("websocket", ...)` -> `framereceived`) để so bảng với số server.

## Bước 4. So trước/sau mỗi tick
```python
def snap(tag):
    return {"tag": tag, "t": time.time(), "board": read_board(),   # từ Bước 3, đã parse số
            "state": pg.evaluate("__state()")}
a = snap("truoc"); pg.wait_for_timeout(TICK_MS*1.5)               # ít nhất 1 tick, đo theo giờ server
b = snap("sau")
delta = b["board"]["diem_ta"] - a["board"]["diem_ta"]
assert delta == DIEM_MOI_TICK * so_tick_da_qua(a, b), (a, b)
```
Việc cần so ở mỗi mốc: (1) bảng == state client == số server; (2) sau 1 tick điểm tăng đúng luật, đội đúng; (3) chủ đồi/đếm ngược đổi đúng lúc đổi trạng thái (chiếm, tranh chấp, trả); (4) vào/ra trụ sở không làm bảng đứng hình hay nhân đôi điểm; (5) hai người dùng (hoặc bot quan sát) thấy cùng số. Cho phép sai số ±1 tick vì độ trễ; dựa vào số tick từ server, không đếm bằng `sleep`. Lưu mọi `snap` vào `probe.json`, và chụp ảnh ở mỗi cặp trước/sau (`NN_<kịch-bản>_truoc/sau.png`).

## Bước 5. Đọc kết quả
- Mở từng ảnh bằng công cụ đọc ảnh, đối chiếu với `probe.json`: chữ không tràn khung, không rỗng, không `NaN`/`undefined`.
- Bảng báo cáo: mỗi kịch bản một dòng `PASS/FAIL`, bước nào lệch (số mong đợi vs bảng vs server), lỗi console/pageerror, bot hay người thật, dữ liệu thật hay giả.
- Lỗi lặp lại được thì ghi chuỗi tái hiện (seed, kịch bản, tick) cho phòng dev.

## Tiêu chí xong
- [ ] Phím E bấm thật (có ca âm: xa cửa, sai đội).
- [ ] Đã xác định mỗi bảng là DOM hay Phaser và dùng đúng cách đọc.
- [ ] Mỗi kịch bản có so trước/sau và so với số server; có `probe.json` + ảnh đã tự xem.
- [ ] Tên tài khoản mới, bot dọn, server nền và Chromium đã tắt.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| E không phản ứng | canvas chưa có tiêu điểm, hoặc `press` quá nhanh so với `update`: click canvas, dùng `down` -> chờ -> `up` |
| `innerText` rỗng nhưng thấy chữ | chữ Phaser: dùng `TEXTS` ở Bước 3 |
| `TEXTS` trả mảng rỗng | `game` chưa lộ, hoặc scene bảng là scene khác (UI scene chạy song song): `getScenes(true)` đã gồm; kiểm tên |
| Điểm lệch ±1 | lấy mốc theo tick server chứ không theo `sleep`; cho phép ±1 tick |
| Bot không vào vùng | bot chưa đặt đội/đích; xem cờ bot trong mã, đừng đoán |
| Kết quả mỗi lần khác | cố định seed, đợi `__ready`, tên tài khoản mới, bot cùng kịch bản |
| Thiếu quyền chạy/ghi `shots/` | `[CẦN SẾP]` một lần, không hỏi lại |
