---
name: kiem-client-man-thi-giay-chung-nhan-playwright
description: Kiểm client CTFClanWar bằng Playwright cho màn thi (ExamPanel), chặn copy (SecureScreen), mục Chứng chỉ (CertPanel), ổ khoá cửa tháp và giấy chứng nhận. Dùng sau khi sửa code trong client/src/cert/ khi cần bằng chứng chạy thật; phòng không được chạy Playwright thì viết script rồi nhờ Tôm hoặc sếp chạy.
---
# Kiểm màn thi + giấy chứng nhận bằng Playwright

## Mục tiêu
Một script ra bảng PASS/FAIL cho 5 nhóm kiểm + ảnh làm bằng chứng. Là kiểm tra khói/giao diện, không thay việc server chấm điểm thật. Chữ trên màn thi và giấy đều **vẽ trên canvas** (không có chữ DOM), nên không dùng `get_by_text`: đọc trạng thái qua móc `__state`/`__debug` (hoặc mã client) và NHÌN ảnh.

Nền chung (cài Playwright, server tĩnh, swiftshader, tài khoản mới, đóng server): xem `chup-anh-man-hinh-game` Bước 0-3b và `choi-thu-headless-kiem-man-nap-ngay-dem-nha-rieng`. Không nhắc lại ở đây.

## Ai chạy
Phòng bị cấm chạy Playwright: chỉ viết `tools/cert_smoke.py` + nêu đúng lệnh chạy, thêm ĐÚNG 1 dòng `[CẦN SẾP] cần Tôm/sếp chạy python tools/cert_smoke.py <url> <thư mục ảnh>`. Không tự suy kết quả khi chưa có `cert_smoke.json`.

## Bước 0. Đọc trước khi viết (không đoán)
- `client/src/cert/certProtocol.ts`: bảng tin nhắn `certGet`, `certLesson`, `examStart`, `examAnswer` (trả `examStep`), `examFocus`. Hợp đồng này do client tự khai, server có thể chưa có → mặc định **giả WebSocket**, ghi "dữ liệu giả" trong báo cáo.
- `client/src/cert/certCatalog.ts` và `content/certs/catalog.json`: lấy id chứng chỉ thật (vd "Nhập môn Web"), số câu, giới hạn giờ.
- `ExamPanel`, `SecureScreen`, `CertPanel`: tìm tên hàm/cờ để vào thẳng màn; chưa có móc thì nhờ phòng dev thêm dưới `?debug=1` (`__state().screen`, `__debug.openExam(id)`, `__debug.openCert()`), hoặc đi bằng điều khiển thật: phím **Z** mở Chứng chỉ (tạm), cửa tháp khoá có nút "Xem chứng chỉ".

## Bước 1. Giả server (Playwright ≥1.48)
```python
def mock(ws):
    server = ws.connect_to_server() if USE_REAL else None   # USE_REAL=False: không nối server thật
    def on_msg(m):
        d = json.loads(m)
        if d["t"] == "examStart":  ws.send(json.dumps(STEP(0)))
        elif d["t"] == "examAnswer": SENT.append(d); ws.send(json.dumps(STEP(len(SENT))))
        elif d["t"] == "examFocus":  FOCUS.append(d)
        elif d["t"] == "certGet":    ws.send(json.dumps(CERT_VIEW))
    ws.on_message(on_msg)
pg.route_web_socket("**/*", mock)   # đặt TRƯỚC pg.goto
```
Tên trường (`t`, `step`, `deadline`...) lấy từ `certProtocol.ts`. Giữ `SENT`/`FOCUS` để assert game đã gửi gì (vd hết giờ → `answer == -1`).

## Bước 2. Năm nhóm kiểm
1. **Màn thi**: vào thi → ảnh `01_cau1`; bấm phím `2` rồi `A-D`; kiểm `SENT[0].answer` đúng đáp án; mỗi lần chỉ 1 câu, không có đường quay lại; `Esc` giữa chừng KHÔNG thoát (state vẫn là màn thi); chờ hết giờ câu (rút `deadline` ngắn trong dữ liệu giả) → game tự gửi `-1`.
2. **Mất tiêu điểm**: `pg.evaluate("window.dispatchEvent(new Event('blur'))")` hoặc mở tab phụ; ảnh thấy cảnh báo đếm 3 giây; `FOCUS` nhận tin `examFocus`.
3. **Chặn copy** (đo bằng `defaultPrevented`, không bằng cảm giác):
```python
r = pg.evaluate("""() => {
  const out = {};
  const fire = (type, init) => { const e = new (type.startsWith('key') ? KeyboardEvent : MouseEvent)(type, {bubbles:true, cancelable:true, ...init});
    document.dispatchEvent(e); return e.defaultPrevented; };
  out.chuot_phai = fire('contextmenu', {});
  for (const k of ['c','x','a','s','u','p']) out['ctrl_'+k] = fire('keydown', {key:k, ctrlKey:true});
  out.f12 = fire('keydown', {key:'F12'});
  for (const k of ['i','j','c']) out['ctrl_shift_'+k] = fire('keydown', {key:k.toUpperCase(), ctrlKey:true, shiftKey:true});
  for (const t of ['copy','cut','paste','dragstart','selectstart']) { const e = new Event(t, {bubbles:true, cancelable:true}); document.dispatchEvent(e); out[t] = e.defaultPrevented; }
  out.co_chu_dom = document.body.innerText.trim().length;   // phải ~0 (chữ vẽ canvas)
  return out; }""")
```
   PASS khi mọi giá trị `True` và `co_chu_dom` ≈ 0. Kiểm cả ở màn bài học (`LessonPanel`). Watermark tên người chơi phải thấy trong ảnh. Chụp màn hình vẫn được là đúng thiết kế, đừng báo lỗi.
4. **Mục Chứng chỉ**: mở bằng Z → ảnh tab Hạ tầng (5×5 + hàng MT1-3) và tab ANM (SEC0 + 10×4); ô có đủ 3 trạng thái (đạt/mở/khoá), ô khoá ghi "Cần: ..."; chọn ô → có đường nối tiên quyết; bấm tiên quyết ở tab kia → nhảy tab; tổng "Đã đạt n / 69" khớp dữ liệu giả.
5. **Cửa tháp + giấy chứng nhận**: (a) dữ liệu giả thiếu chứng chỉ → cửa khoá, hiện "Cần chứng chỉ ...", nút "Xem chứng chỉ" mở đúng ô; (b) bậc không đủ → khoá riêng; (c) KHÔNG có dữ liệu chứng chỉ → client không tự khoá; (d) dữ liệu giả có chứng chỉ đạt → mở giấy: ảnh `05_giay` đủ tên, chứng chỉ, ngày, điểm, mã, bậc, huy hiệu con dấu.

## Bước 3. Đọc kết quả
- Mở TỪNG ảnh bằng công cụ đọc ảnh: chữ trên giấy nằm đúng khung của `ui_cert_paper` (phóng ×2), không tràn/đè con dấu; tên dài và có dấu tiếng Việt không bị cắt. Đây là phần trước đó mới đo bằng mắt từ art, chưa nhìn trong game.
- Ghi `cert_smoke.json`: mỗi nhóm `{pass, note}`, danh sách lỗi console/pageerror/requestfailed, "dữ liệu giả" hay server thật.
- Báo cáo: bảng 5 dòng, đường dẫn ảnh, lỗi console, chỗ nào chỉ kiểm bằng giả WS.

## Tiêu chí xong
- [ ] Đã chạy thật, có `cert_smoke.json` và ảnh; ảnh đã tự mở xem.
- [ ] Mỗi nhóm có PASS/FAIL riêng, FAIL ghi bước nào.
- [ ] Ghi rõ dữ liệu giả hay thật; hợp đồng tin nhắn chưa được Tôm xác nhận thì nói rõ.
- [ ] Dùng tên tài khoản mới (`cert_<epoch>`), tắt server nền, Chromium không treo.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| Route WS không bắt được | `route_web_socket` đặt sau `goto`, hoặc mẫu URL sai: đặt trước, dùng `**/*` |
| Màn thi không hiện | game chờ `examStep` đầu: giả đủ `examStart` → `examStep`; xem tên kiểu trong `certProtocol.ts` |
| Test copy đều `False` | sự kiện gắn ở `window`/canvas chứ không phải `document`: bắn vào đúng đích (đọc `SecureScreen`) |
| `innerText` khác 0 | còn chữ DOM (nút, overlay): chỉ ra phần tử, báo phòng dev |
| Phím Z không mở | đang ở màn chọn nhân vật (giữ mọi phím): tạo nhân vật trước |
| Hết giờ không gửi `-1` | đồng hồ theo giờ server: dữ liệu giả phải có `deadline` tính theo `serverTime` mà game dùng |
| Test cert đỏ ở `propInfo.test.ts` | lỗi có sẵn, không thuộc phần này; chỉ ghi chú |
| Thiếu quyền chạy/ghi `shots/` | `[CẦN SẾP]` một lần, không hỏi lại |
