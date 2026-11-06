---
name: do-hieu-nang-game-headless
description: Đo FPS, số draw call, bộ nhớ heap của game web (Phaser/canvas) bằng Chromium headless (Playwright) nhẹ CPU, để có số trước/sau khi tối ưu mà không phải chạy playtest nặng. Dùng khi sửa render/sprite/hạt/scene và cần chứng minh nhanh hơn hay nhẹ hơn.
---
# Đo hiệu năng game trong trình duyệt headless

## Mục tiêu
Một bảng số **trước/sau** (FPS median, p5 FPS, draw call/khung, heap MB) đo cùng máy, cùng kịch bản, ghi ra JSON để dán vào báo cáo. Đây là phép đo **tương đối** để so sánh; không phải FPS thật trên máy người chơi.

## Giới hạn phải nói thẳng trong báo cáo
- Headless dùng GL phần mềm (SwiftShader) nên FPS tuyệt đối thấp và phụ thuộc CPU. Chỉ so sánh before/after trên **cùng máy, cùng lệnh**. Không viết "game đạt 60 FPS" từ số này.
- Draw call và heap ít phụ thuộc máy hơn FPS, nên là bằng chứng chắc hơn.

## Bước 0. Điều kiện
- Cần Playwright + chromium (xem `chup-anh-man-hinh-game`, Bước 0; kiểm `python -c "import playwright"`). Thiếu quyền cài/chạy thì hỏi sếp ĐÚNG 1 LẦN bằng `[CẦN SẾP]`.
- Chạy game cục bộ như `chup-anh-man-hinh-game` Bước 1 (`python -m http.server <cổng>`, không `file://`). Lệnh gõ trần, không `export`/`X=2 python`; văn phòng đã đặt sẵn 2 thread.
- Máy yên: không chạy build/playtest khác song song, nếu không FPS nhiễu.

## Bước 1. Giữ nhẹ CPU
- Viewport nhỏ nhưng đúng tỉ lệ game (vd 640×360, `device_scale_factor=1`); mọi lượt đo dùng cùng cỡ.
- Một tab, một trình duyệt; đóng ngay khi xong. Thời gian đo ngắn: khởi động 3 s + đo 10 s, lặp 3 lượt (tiến trình mới mỗi lượt).
- Cờ: `--use-gl=swiftshader --enable-unsafe-swiftshader --disable-background-timer-throttling`.
- Cố định kịch bản: `?seed=42&scene=...` hoặc cờ `__ready`; không phụ thuộc người bấm.

## Bước 2. Script mẫu (`tools/perf.py`)
```python
import sys, json, statistics as st
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
WARM, DUR, RUNS = 3000, 10000, 3

HOOK = """
window.__dc = 0;
for (const C of [WebGLRenderingContext, window.WebGL2RenderingContext]) {
  if (!C) continue;
  for (const f of ['drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced']) {
    const o = C.prototype[f]; if (!o) continue;
    C.prototype[f] = function(...a){ window.__dc++; return o.apply(this, a); };
  }
}
window.__ft = [];
(function loop(t){ window.__ft.push(t); requestAnimationFrame(loop); })(performance.now());
"""

def one_run(p):
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader",
                                "--disable-background-timer-throttling"])
    pg = b.new_page(viewport={"width": 640, "height": 360}, device_scale_factor=1)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(HOOK)
    pg.goto(url, wait_until="networkidle"); pg.wait_for_selector("canvas")
    pg.wait_for_timeout(WARM)
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("Performance.enable")
    cdp.send("HeapProfiler.collectGarbage")          # heap đo sau GC, đỡ nhiễu
    pg.evaluate("window.__dc = 0; window.__ft = []")
    pg.wait_for_timeout(DUR)
    ft = pg.evaluate("window.__ft"); dc = pg.evaluate("window.__dc")
    m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    b.close()
    dt = [ft[i+1] - ft[i] for i in range(len(ft) - 1)]
    fps = sorted(1000 / d for d in dt if d > 0)
    return {"frames": len(ft), "fps_median": st.median(fps),
            "fps_p5": fps[int(len(fps) * 0.05)],
            "draw_calls_per_frame": dc / max(len(ft), 1),
            "heap_mb": m["JSHeapUsedSize"] / 1048576, "page_errors": errs}

with sync_playwright() as p:
    runs = [one_run(p) for _ in range(RUNS)]
res = {k: st.median(r[k] for r in runs) for k in
       ("fps_median", "fps_p5", "draw_calls_per_frame", "heap_mb")}
res.update(url=url, runs=runs, viewport="640x360", warm_ms=WARM, dur_ms=DUR)
json.dump(res, open(out, "w"), indent=2)
print(json.dumps({k: res[k] for k in ("fps_median", "fps_p5", "draw_calls_per_frame", "heap_mb")}))
```
Chạy: `python tools/perf.py http://localhost:8123/?seed=42 perf/before.json`

## Bước 3. Quy trình trước/sau
1. Đo `perf/<việc>/before.json` **trước** khi sửa.
2. Sửa code. Đo lại đúng lệnh → `after.json`.
3. Đo lại `before` bằng lệnh y hệt nếu nghi nhiễu (chạy 2 lần cùng bản, lệch quá ~10% là máy ồn).
4. Bảng báo cáo:

| Chỉ số | Trước | Sau | Đổi |
|---|---|---|---|
| FPS median | | | |
| FPS p5 | | | |
| Draw call/khung | | | |
| Heap (MB) | | | |

5. Ghi kèm: máy, số lượt, viewport, kịch bản, lỗi trang (`page_errors`).

## Heap rò rỉ (tuỳ chọn)
Đo `heap_mb` ở giây 5 và giây 60 sau `HeapProfiler.collectGarbage`. Tăng đều theo thời gian khi kịch bản không đổi là nghi rò (sprite/tween/listener không huỷ).

## Số draw call từ chính Phaser (đối chiếu)
Nếu hook GL bị chặn, đọc từ game: Phaser WebGL có thể đếm batch trong pipeline; tên trường đổi theo phiên bản nên kiểm trong console trước, đừng đoán. Hook GL ở trên không phụ thuộc phiên bản.

## Tiêu chí xong
- [ ] Có `before.json` và `after.json`, mỗi file 3 lượt, cùng lệnh/viewport/kịch bản.
- [ ] Bảng 4 chỉ số trước/sau, đã nói rõ giới hạn SwiftShader.
- [ ] `page_errors` rỗng hoặc đã báo lỗi nào còn.
- [ ] Đã tắt server nền; không để Chromium treo.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| FPS luôn đúng 60 hoặc 0 | game chưa vào scene: chờ `__ready`/tăng WARM; kiểm console 404 |
| `draw_calls_per_frame` = 0 | game dùng Canvas 2D, không phải WebGL: đo số lệnh `drawImage` bằng hook `CanvasRenderingContext2D.prototype.drawImage` tương tự |
| Hook không chạy | `add_init_script` phải gọi TRƯỚC `goto` |
| Số nhảy lung tung giữa các lượt | máy đang bận; dừng job khác, tăng DUR, báo median 3 lượt |
| FPS before/after khác do random | cố định `seed`, tắt hiệu ứng ngẫu nhiên |
| Heap tụt bất thường | thiếu `collectGarbage` trước khi đọc |
| Dùng FPS headless làm kết luận cho người chơi | chỉ kết luận "nhanh hơn/chậm hơn x%" trên cùng máy |
