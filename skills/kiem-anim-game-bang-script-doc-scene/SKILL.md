---
name: kiem-anim-game-bang-script-doc-scene
description: Kiểm animation trong game Phaser (số anim đã tạo, sprite decor có đang phát không) bằng một script ngắn đọc trạng thái scene, không chạy cả hành trình playtest. Dùng sau khi thêm/sửa anim, spritesheet decor, hoặc khi nghi anim không tạo/không chạy.
---
# Kiểm anim bằng script đọc scene

## Mục tiêu
Vào thẳng đúng màn (vài giây), đọc trực tiếp từ Phaser: (a) anim nào đã `anims.create`, (b) sprite nào đang phát anim gì, đứng hay chạy. In bảng PASS/FAIL + JSON. Là kiểm tra **khói số liệu**; muốn biết đẹp/mượt thì vẫn NHÌN ảnh (xem `chup-anh-man-hinh-game`). Không thay playtest hành trình (`tools/playtest/journey.mjs`).

## Khi nào không dùng
- Chỉ cần xem hình spritesheet/khung neo: `trang-xem-truoc-khung-neo-sprite`.
- Đo FPS/hiệu năng: `do-hieu-nang-game-headless`.

## Bước 0. Điều kiện
- Playwright + chromium + server tĩnh/dev (không `file://`): xem `chup-anh-man-hinh-game` Bước 0-1. Lệnh gõ trần `python ...` / `node ...`, không `export`, không `X=2 python`.
- Chưa được chạy lệnh: viết script, nộp, thêm ĐÚNG 1 dòng `[CẦN SẾP] cần quyền chạy <lệnh>`; không tự đoán kết quả.
- Tài khoản/bản server: dùng tên mới `smoke_<epoch>`, không đụng dữ liệu thật.

## Bước 1. Tìm "móc" để vào thẳng màn và lấy game
Đọc mã trước, KHÔNG đoán tên:
1. Cách lấy đối tượng game: `window.game`, `window.__game`, hay `__state()`. Chưa lộ thì thêm dưới `?debug=1` (việc sửa client của phòng dev): `window.__game = game`.
2. Cách vào thẳng màn: `?scene=<Key>`, `__debug.goto('<Key>')`, hoặc điều khiển thật (đi tới cửa + `E`). Nhớ: scene trong nhà (vd Base) chỉ tồn tại SAU khi vào nhà; lấy sớm sẽ ra `undefined`.
3. Danh sách anim kỳ vọng: đọc chỗ `anims.create` trong mã/asset manifest, ghi ra danh sách `key` + số khung. Đó là "đáp án" để so.

## Bước 2. Đoạn đọc trạng thái (chạy trong trang bằng `page.evaluate`)
Tên API đổi theo phiên bản Phaser: kiểm lại trong mã.
```js
(() => {
  const g = window.__game || window.game;
  const sc = g.scene.getScenes(true);                         // scene đang chạy
  const anims = g.anims.anims.entries;                        // toàn cục: { key: Animation }
  const created = Object.keys(anims);
  const scenes = sc.map(s => ({
    scene: s.scene.key,
    sprites: s.children.list
      .filter(o => o.type === 'Sprite' && o.anims)
      .map(o => ({
        tex: o.texture?.key, x: Math.round(o.x), y: Math.round(o.y),
        visible: o.visible, alpha: o.alpha,
        anim: o.anims.currentAnim?.key ?? null,
        playing: o.anims.isPlaying, frame: o.anims.currentFrame?.index ?? null,
      })),
  }));
  return { created: created.length, keys: created, scenes };
})()
```
Phát hiện "đang phát" thật sự: đọc `frame` hai lần cách ~500 ms; nếu `playing` true mà `frame` không đổi → nghi `frameRate` quá thấp hoặc 1 khung.

## Bước 3. Script mẫu (`tools/check_anim.py`)
```python
import sys, json
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]          # vd "http://localhost:8123/?debug=1&scene=Base"
expect = sys.argv[3].split(",") if len(sys.argv) > 3 else []   # key anim kỳ vọng
READ = open("tools/read_anim.js").read()      # đoạn JS ở Bước 2 (một biểu thức)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url, wait_until="domcontentloaded")
    pg.wait_for_function("window.__ready === true", timeout=30000)
    pg.wait_for_timeout(1500)
    a = pg.evaluate(READ)
    pg.wait_for_timeout(500)
    c = pg.evaluate(READ)
    pg.screenshot(path=f"{out}.png")
    b.close()

missing = [k for k in expect if k not in a["keys"]]
spr = [s for sc in a["scenes"] for s in sc["sprites"]]
playing = [s for s in spr if s["playing"] and s["visible"]]
f0 = {(s["tex"], s["x"], s["y"]): s["frame"] for s in playing}
moving = [s for sc in c["scenes"] for s in sc["sprites"]
          if s["playing"] and f0.get((s["tex"], s["x"], s["y"])) not in (None, s["frame"])]
res = {"tao": a["created"], "thieu": missing, "dang_phat": len(playing),
       "frame_doi": len(moving), "loi_console": errs,
       "tong": "PASS" if not missing and playing and moving and not errs else "FAIL"}
json.dump({**res, "chi_tiet": a}, open(f"{out}.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=2))
```
Chạy: `python tools/check_anim.py "http://localhost:8123/?debug=1&scene=Base" shots/anim/base "hero-run,decor-lua,decor-quat"` (tạo `shots/anim` trước). Bản Node (`.mjs`) làm tương tự nếu repo đã dùng `tools/playtest/*.mjs`: cùng đoạn `page.evaluate`.

## Bước 4. Đọc kết quả và báo cáo
1. `thieu` rỗng: mọi key kỳ vọng đã tạo. Có thiếu → anim chưa `create` (sai thứ tự nạp, scene chưa vào, key gõ sai).
2. `dang_phat` > 0 và `frame_doi` > 0 cho sprite decor đã biết (đối chiếu theo `tex`). Sprite decor `playing:false` → thiếu `.play(key)` hoặc `repeat` sai.
3. Mở ảnh `.png` và NHÌN: decor có hiện, đúng chỗ, không đen.
4. Báo cáo: `## Tóm tắt` + bảng `key | đã tạo | sprite dùng | playing | frame đổi`, lỗi console, màn đã vào và cách vào, dữ liệu thật hay giả.

## Tiêu chí xong
- [ ] Đã chạy thật (có `.json` + `.png`), không suy đoán.
- [ ] Có danh sách key kỳ vọng lấy từ mã, so với `created`.
- [ ] Mỗi sprite decor quan tâm có dòng riêng (anim, playing, frame đổi).
- [ ] Đã mở ảnh xem; đóng Chromium, tắt server nền.

## Lỗi hay gặp
| Triệu chứng | Cách xử lý |
|---|---|
| `getScenes(true)` rỗng / thiếu scene Base | chưa vào đúng màn hoặc chưa vào nhà: đi tới cửa + `E` rồi mới đọc |
| `created` = 0 | anim tạo trong `create` của scene chưa chạy; chờ `__ready`, hoặc anim tạo theo scene (`this.anims` cục bộ) - đọc `s.anims` thay `g.anims` |
| Key có nhưng sprite `anim:null` | quên `.play(key)`; hoặc key trùng bị `exists` chặn tạo lại |
| `playing:true` mà `frame` đứng | `frameRate` thấp / chỉ 1 khung / game bị tạm dừng (tab nền): thêm `pg.bring_to_front()` |
| `type !== 'Sprite'` bỏ sót decor | decor là Container/Image/Spine: lọc theo `o.anims` thay `o.type`, hoặc duyệt `o.list` |
| Chạy lệnh bị chặn | có `export`/`X=2 python`: bỏ; thiếu quyền: `[CẦN SẾP]` đúng 1 lần |
