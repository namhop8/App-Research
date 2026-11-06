---
name: chup-anh-man-hinh-game
description: Chụp ảnh màn hình game web (Phaser/canvas) tự động bằng trình duyệt headless (Playwright) để kèm ảnh trước/sau cho sếp. Dùng khi sửa giao diện/art/hành vi game và cần bằng chứng hình ảnh, hoặc khi cần ảnh đúng cùng trạng thái để so sánh. Có phần riêng cho CTFClanWar - đưa game về "tài khoản mới, chưa chọn nhân vật" để chụp màn chọn nhân vật và tủ đồ ở 1280×720.
---
# Chụp ảnh màn hình game tự động (Playwright)

## Mục tiêu
Mỗi thay đổi nhìn thấy được có cặp ảnh `before` / `after` cùng khung hình, cùng trạng thái game, đặt tên rõ, để sếp xem ngay không phải tự chạy game.

## Bước 0. Cài một lần (cần quyền chạy lệnh; hỏi sếp ĐÚNG 1 LẦN nếu thiếu)
```
pip install playwright
python -m playwright install chromium
```
Nếu dự án dùng Node: `npm i -D playwright` rồi `npx playwright install chromium`. Kiểm có sẵn trước khi cài: `python -c "import playwright"`.

## Bước 1. Chạy game cục bộ
- Game tĩnh (index.html): `python -m http.server 8123` trong thư mục game (chạy nền). KHÔNG mở bằng `file://` vì Phaser tải asset bị chặn CORS.
- Game dùng bundler: chạy dev server của dự án (vd `npm run dev`), lấy URL in ra.
- Mỗi job nền tối đa 2 thread; gõ lệnh trần, không `export`/`X=2 python`.

## Bước 2. Script chụp mẫu (`tools/shot.py`)
```python
import sys, time
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]          # vd http://localhost:8123/?debug=1  shots/after_menu.png
wait_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 1500

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_selector("canvas")
    pg.wait_for_timeout(wait_ms)             # chờ asset + hoạt ảnh vào trạng thái ổn định
    pg.locator("canvas").first.screenshot(path=out)   # chỉ chụp canvas, bỏ viền trang
    b.close()
print("saved", out, "| loi console:", errs or "khong")
```
Chạy: `python tools/shot.py http://localhost:8123/ shots/after_menu.png`

## Bước 3. Đưa game vào đúng trạng thái trước khi chụp
Chụp ngay sau load thường ra màn hình đen/loading. Cách làm cho ảnh lặp lại được:
- **Đợi cờ sẵn sàng**: game đặt `window.__ready = true` khi scene vào xong, rồi `pg.wait_for_function("window.__ready === true")`. Tốt hơn chờ cố định.
- **Tham số URL**: `?scene=Race&seed=42&debug=1` để vào thẳng màn cần chụp, cố định random.
- **Điều khiển**: `pg.keyboard.press("Enter")`, `pg.mouse.click(640, 360)`; giữ phím: `keyboard.down("ArrowRight")`, chờ, `keyboard.up(...)`.
- **Đóng băng khung**: cho game đọc `?freeze=1` hoặc gọi `pg.evaluate("game.loop.sleep()")` ngay trước khi chụp để ảnh không nhoè theo chuyển động.
- Pixel art: `device_scale_factor=1` và viewport là bội nguyên của độ phân giải game, để không bị mờ do nội suy.

## Bước 3b. CTFClanWar: trạng thái "tài khoản mới, chưa chọn nhân vật"
Màn chọn nhân vật (`wardrobe/CharacterPick.ts`, 3 thẻ Khoa/Linh/Bảo + "Bắt đầu") chỉ hiện khi **server** báo `created = false`, tức tài khoản chưa từng gửi `wardrobeCreate`. Client không tự giữ cờ này (không phải localStorage), nên xoá localStorage KHÔNG đưa game về trạng thái này. Phải đổi phía server/tài khoản. Chọn một trong ba cách, theo thứ tự ưu tiên:

1. **Tài khoản tên mới mỗi lần chạy** (đơn giản nhất): đăng nhập bằng tên duy nhất, vd `shot_<epoch>`, để server coi là chưa tạo ngoại hình. Không đụng dữ liệu người chơi thật.
2. **Server chạy với kho dữ liệu tạm**: trỏ server sang thư mục dữ liệu rỗng riêng cho lượt chụp (xem `server/wardrobeStore.ts` để biết cấu hình đường dẫn/kho). Chỉ dùng thư mục tạm; KHÔNG xoá hay ghi đè kho thật.
3. **Giả tin WebSocket** (khi server chưa nối `wardrobe*`, hoặc không đổi được server): Playwright ≥1.48 có `page.route_web_socket`, trả về view với `created=false`. Ảnh kiểu này chỉ chứng minh giao diện, ghi rõ "dữ liệu giả" trong báo cáo.

Cách đăng nhập/tạo tài khoản và biến cấu hình cụ thể: đọc `package.json` (script `play`) và mã đăng nhập trong `client/` rồi điền vào script; kỹ năng này chưa kiểm trực tiếp trên mã game.

Chuỗi chụp (một phiên, một viewport 1280×720, `device_scale_factor=1`):
```python
pg.goto(f"{url}?...")                       # tên tài khoản mới như trên
pg.wait_for_selector("canvas")
pg.wait_for_timeout(2000)                   # hoặc chờ cờ __ready nếu game có
shot("01_chon_nhan_vat_mac_dinh")           # CHƯA bấm gì: màn chọn phải hiện
for i, (x, y) in enumerate(THE_NHAN_VAT):   # toạ độ 3 thẻ đo từ ảnh 01
    pg.mouse.click(x, y); pg.wait_for_timeout(300)
    shot(f"02_the_{i+1}_da_chon")
pg.mouse.click(*NUT_BAT_DAU)                # gửi wardrobeCreate
pg.wait_for_timeout(1500)
shot("03_sau_khi_chon_ngoai_pho")
pg.keyboard.press("c"); pg.wait_for_timeout(500)
shot("04_tu_do_phim_C")                     # đóng bằng Esc rồi chụp thêm tab/bậc nếu cần
```
- Toạ độ thẻ/nút: chụp ảnh 01, mở xem, đo bằng mắt rồi điền hằng số. Không đoán.
- Màn chọn giữ mọi phím và không đóng được bằng Esc; chỉ đi tiếp bằng chọn thẻ + "Bắt đầu".
- Tiệm thời trang: đi tới chủ tiệm (mã quầy `thoi_trang`), bấm phím tương tác **Q**, chụp màn shop riêng.
- Kiểm kích thước: `Image.open(f).size == (1280, 720)` nếu chụp cả khung; chụp riêng canvas mà ra khác 1280×720 thì game đang scale, kiểm viewport/Scale mode.
- Chạy qua `npm run play` nếu dự án đã có sẵn; không nhân đôi server nếu cổng đã có.
- Tài khoản đã tạo xong thì không quay lại `created=false` được: muốn chụp lại màn chọn, dùng tên mới.

## Bước 4. Quy trình trước/sau
1. Trước khi sửa: chụp `shots/<việc>/before_<màn>.png`.
2. Sửa code.
3. Chạy lại đúng lệnh, cùng URL/seed/viewport: `shots/<việc>/after_<màn>.png`.
4. (Tuỳ chọn) ghép cạnh nhau:
```python
from PIL import Image
a, b = Image.open("before.png"), Image.open("after.png")
c = Image.new("RGB", (a.width + b.width + 10, max(a.height, b.height)), "white")
c.paste(a, (0, 0)); c.paste(b, (a.width + 10, 0)); c.save("compare.png")
```
5. Mở từng ảnh bằng công cụ đọc ảnh và NHÌN thật, đừng chỉ tin file đã tạo ra.
6. Báo cáo: liệt kê đường dẫn ảnh, nói rõ khác gì giữa trước và sau, kèm số lỗi console.

## Tiêu chí xong
- [ ] Có đủ cặp before/after, cùng viewport và trạng thái.
- [ ] Ảnh không đen, không dừng ở màn loading, đã tự mở xem.
- [ ] Console không lỗi (hoặc báo rõ lỗi nào còn).
- [ ] Tên file `before_/after_` + tên màn; lưu trong thư mục được phép ghi của phòng.
- [ ] Đã tắt server nền sau khi chụp xong.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| Ảnh đen toàn bộ | WebGL headless: thêm args swiftshader như mẫu, hoặc cấu hình Phaser `type: Phaser.CANVAS` khi `?debug` |
| Ảnh là màn loading | dùng cờ `__ready` hoặc tăng `wait_ms`; kiểm tên asset 404 trong console |
| `file://` lỗi tải asset | chạy `python -m http.server` thay vì mở file |
| Ảnh trước/sau lệch nhau dù không đổi gì | cố định `seed`, tắt hạt/hiệu ứng ngẫu nhiên, đóng băng khung |
| Pixel art bị mờ | `device_scale_factor=1`, CSS `image-rendering: pixelated`, `pixelArt: true` |
| `locator("canvas")` timeout | game chưa tạo canvas: kiểm console, đúng URL/cổng chưa |
| Cổng 8123 đã dùng | đổi cổng khác, hoặc tắt server cũ |
| Màn chọn nhân vật không hiện | tài khoản đã tạo ngoại hình, hoặc server cũ chưa hỗ trợ `wardrobe*` (màn bị ẩn): dùng tên mới / kho tạm / giả WS |
| Xoá localStorage mà vẫn không về "tài khoản mới" | cờ `created` nằm ở server, đổi tài khoản hoặc kho server |
| Tủ đồ báo "Server chưa hỗ trợ tủ đồ" | server chưa nối `wardrobe*`; chụp được nhưng mua/lưu bị chặn, ghi rõ vào báo cáo |
| Thiếu quyền chạy lệnh/ghi `shots/` | hỏi sếp một lần bằng `[CẦN SẾP]`, không hỏi lại |
