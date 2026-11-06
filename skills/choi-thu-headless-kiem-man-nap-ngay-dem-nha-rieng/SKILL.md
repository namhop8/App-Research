---
name: choi-thu-headless-kiem-man-nap-ngay-dem-nha-rieng
description: Chạy thử (smoke test) game web Phaser bằng Playwright headless để kiểm 3 thứ - màn nạp (loading) vào được game, đổi ngày/đêm, vào/ra nhà riêng - và trả kết quả PASS/FAIL kèm lỗi console. Dùng sau khi sửa scene/nạp asset/chu kỳ ngày đêm/nhà riêng mà không muốn tự chơi tay.
---
# Chạy thử headless: màn nạp, ngày/đêm, vào nhà riêng

## Mục tiêu
Một script chạy một lần, in bảng PASS/FAIL cho 3 kiểm tra, lưu ảnh làm bằng chứng, kèm số lỗi console/trang. Đây là kiểm tra **khói** (có chạy được không), không thay playtest cảm nhận.

## Ai được chạy
Nếu phòng bạn bị cấm chạy Playwright: viết script và nộp, rồi thêm một dòng `[CẦN SẾP] cần quyền chạy python tools/smoke.py (Playwright, localhost)` ĐÚNG 1 LẦN. Người/phòng có quyền chạy sẽ chạy đúng lệnh đó và trả JSON. Không tự suy ra kết quả khi chưa chạy.

## Bước 0. Điều kiện
- Cài Playwright + chromium, chạy server tĩnh/dev: xem `chup-anh-man-hinh-game` Bước 0-1 (không `file://`). Lệnh gõ trần, không `export`/`X=2 python`.
- Bản dùng server (CTFClanWar): dùng tên tài khoản mới mỗi lượt (`smoke_<epoch>`), không đụng dữ liệu thật; xem `chup-anh-man-hinh-game` Bước 3b.
- Một lượt = một trình duyệt, đóng ngay khi xong; tắt server nền sau đó.

## Bước 1. Khai báo "móc kiểm" trong game (làm một lần)
Đừng đoán trạng thái qua pixel. Cho game lộ ra, chỉ khi `?debug=1`:
```js
window.__ready = false;                 // true khi scene chính nạp xong
window.__state = () => ({ scene: game.scene.getScenes(true)[0]?.scene.key,
                          phase: world.dayPhase,      // 'day' | 'night' (tên thật theo mã)
                          clock: world.clockMs,
                          inHome: !!player.homeId });
window.__debug = { setTime: (ms)=>{...}, enterHome: ()=>{...}, exitHome: ()=>{...} };
```
Tên trường/hàm là gợi ý: đọc mã game để dùng đúng tên, KHÔNG đoán. Nếu game chưa có móc, thêm trước (đây là việc sửa client của phòng dev), hoặc dùng đường điều khiển thật (đi tới cửa nhà, bấm phím tương tác) và đọc trạng thái qua `__state`.

## Bước 2. Script mẫu (`tools/smoke.py`)
```python
import sys, json, time
from playwright.sync_api import sync_playwright

base = sys.argv[1]                      # vd http://localhost:8123/?debug=1&user=smoke_
outdir = sys.argv[2]                    # vd shots/smoke
user = f"smoke_{int(time.time())}"
url = base + user if base.endswith("=") else base
res, errs = {}, []

def check(name, fn):
    try: ok, note = fn()
    except Exception as e: ok, note = False, f"ngoai le: {e}"
    res[name] = {"pass": bool(ok), "note": note}

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("requestfailed", lambda r: errs.append("404/fail " + r.url))

    # 1. Man nap: canvas len, __ready true trong han, khong ket o loading
    def loading():
        t0 = time.time()
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_selector("canvas", timeout=15000)
        pg.wait_for_function("window.__ready === true", timeout=30000)
        pg.screenshot(path=f"{outdir}/01_sau_nap.png")
        return True, f"vao game sau {time.time()-t0:.1f}s"
    check("man_nap", loading)

    # 2. Ngay/dem: dat gio ngay -> doc phase; dat gio dem -> phase doi; chup ca hai
    def daynight():
        pg.evaluate("__debug.setTime(__debug.DAY_MS ?? 0)"); pg.wait_for_timeout(800)
        a = pg.evaluate("__state().phase"); pg.screenshot(path=f"{outdir}/02_ngay.png")
        pg.evaluate("__debug.setTime(__debug.NIGHT_MS ?? 1e9)"); pg.wait_for_timeout(800)
        c = pg.evaluate("__state().phase"); pg.screenshot(path=f"{outdir}/03_dem.png")
        return a != c, f"phase {a} -> {c}"
    check("ngay_dem", daynight)

    # 3. Nha rieng: vao -> inHome true, scene/map doi; ra -> ve ngoai pho
    def home():
        s0 = pg.evaluate("__state()")
        pg.evaluate("__debug.enterHome()"); pg.wait_for_timeout(1500)
        s1 = pg.evaluate("__state()"); pg.screenshot(path=f"{outdir}/04_trong_nha.png")
        pg.evaluate("__debug.exitHome()"); pg.wait_for_timeout(1500)
        s2 = pg.evaluate("__state()")
        ok = (not s0["inHome"]) and s1["inHome"] and (not s2["inHome"])
        return ok, f"{s0['scene']} -> {s1['scene']} -> {s2['scene']}"
    check("nha_rieng", home)
    b.close()

res["loi_console"] = errs
res["tong"] = "PASS" if all(v["pass"] for k, v in res.items() if k not in ("loi_console",)) and not errs else "FAIL"
json.dump(res, open(f"{outdir}/smoke.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=2))
```
Chạy: `python tools/smoke.py "http://localhost:8123/?debug=1" shots/smoke` (tạo thư mục `shots/smoke` trước).

## Bước 3. Đọc kết quả
1. Mở từng ảnh `01..04` bằng công cụ đọc ảnh và NHÌN: không đen, không kẹt loading, đêm tối hơn ngày thật, trong nhà đúng nội thất.
2. `ngay_dem` PASS chỉ khi phase đổi; nên so thêm độ sáng trung bình 2 ảnh (`PIL.ImageStat.Stat(img.convert("L")).mean`) - đêm phải thấp hơn ngày.
3. Báo cáo: bảng 3 dòng PASS/FAIL, đường dẫn ảnh, danh sách lỗi console, thời gian nạp, cách vào trạng thái (móc debug hay điều khiển thật).
4. Có chạy server thật nối WebSocket thì nói rõ; dùng WS giả thì ghi "dữ liệu giả".

## Tiêu chí xong
- [ ] Đã chạy thật (có `smoke.json`), không suy đoán.
- [ ] 3 kiểm tra có kết quả riêng, FAIL ghi rõ ở bước nào.
- [ ] Ảnh đã tự mở xem; console không lỗi hoặc đã liệt kê.
- [ ] Đã tắt server nền, Chromium không treo.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| `__ready` không bao giờ true | scene lỗi giữa chừng: xem `loi_console`, asset 404; hoặc game chưa đặt cờ |
| Ảnh đen | thêm args swiftshader như mẫu, hoặc `type: Phaser.CANVAS` khi `?debug` |
| Ngày/đêm không đổi | chu kỳ chạy theo giờ server, `setTime` chỉ đổi client: dùng đúng nguồn giờ, hoặc chờ đủ thời gian thật |
| `__debug` undefined | `?debug=1` thiếu, hoặc game chưa có móc (Bước 1) |
| Vào nhà không đổi scene | chưa đứng cạnh cửa/chưa có quyền sở hữu nhà: tài khoản mới có thể chưa có nhà riêng, tạo nhà trước hoặc dùng `__debug` |
| Kết quả lệch giữa lần chạy | cố định `seed`, đợi `__ready`, dùng tên tài khoản mới |
| Thiếu quyền chạy lệnh/ghi `shots/` | hỏi sếp một lần bằng `[CẦN SẾP]`, không hỏi lại |
