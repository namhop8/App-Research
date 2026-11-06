---
name: pixel-art-phaser-spritesheet
description: Nạp, cắt khung và chạy hoạt ảnh spritesheet pixel art trong Phaser 3 mà không bị mờ, lệch khung hay rò viền. Dùng khi Phòng Game làm nhân vật, tile, hiệu ứng pixel art (vd cyber city) hoặc khi sprite hiện sai khung, bị nhoè khi phóng to.
---
# Pixel art + spritesheet trong Phaser 3

## Nguồn gốc (không tự bịa)
Kỹ năng này chắt lọc từ các nguồn đã kiểm, không phải bản tự nghĩ:
- Tài liệu chính thức Phaser: <https://docs.phaser.io/phaser/concepts/animations> và API `Loader.LoaderPlugin#spritesheet`.
- Skill `phaser-gamedev` của chongdashu (giấy phép MIT), repo <https://github.com/chongdashu/phaserjs-oakwoods>, đường dẫn `.codex/skills/phaser-gamedev/` (có `reference/spritesheets-nineslice.md`). Quy tắc "đo asset trước khi viết loader" ở Bước 1 lấy từ đây.
- Skill `phaser-best-practices` (onmax/nuxt-skills) cho `pixelArt`/`roundPixels`.
Muốn dùng bản gốc đầy đủ: `npx skills add https://github.com/chongdashu/phaserjs-oakwoods --skill phaser-gamedev` (chạy lệnh cần sếp duyệt qua Thư ký). Ghi chú: các phần dưới đây là bản rút gọn bằng tiếng Việt, chưa đối chiếu từng dòng với repo gốc; khi lệch thì tin tài liệu Phaser đúng phiên bản đang dùng (`npm ls phaser`).

## Bước 1. Đo asset TRƯỚC khi viết loader
Không đoán `frameWidth/frameHeight`. Mỗi sheet đo riêng (idle, run, attack có thể khác cỡ khung).
```python
from PIL import Image
im = Image.open("assets/hero_run.png"); print(im.size)   # (W, H)
```
Công thức kiểm: `W = cols*fw + (cols-1)*spacing + 2*margin` (tương tự cho H). Phải chia đúng, không dư pixel. Thử khung vuông trước với nhân vật. Không khớp → có spacing/margin, hoặc đoán sai cỡ.

## Bước 2. Cấu hình game cho pixel art
```js
const config = {
  type: Phaser.AUTO,
  width: 320, height: 180,            // độ phân giải "gốc" nhỏ, vd 16:9
  pixelArt: true,                     // NEAREST filter, tắt antialias, bật roundPixels
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  physics: { default: 'arcade', arcade: { gravity: { y: 0 } } },
  scene: [Boot, Game],
};
```
- Dựng cảnh ở độ phân giải gốc rồi để `Scale` phóng to; không tự `setScale(3.37)` kiểu số lẻ cho từng sprite (gây pixel không đều). Cần phóng sprite riêng thì dùng số nguyên.
- Chỉ một texture bị mờ: `this.textures.get('hero').setFilter(Phaser.Textures.FilterMode.NEAREST)`.
- Toạ độ nên là số nguyên (`roundPixels` đã giúp); camera cuộn dùng `cameras.main.setRoundPixels(true)`.

## Bước 3. Nạp spritesheet (trong `preload`, không nạp ở `create`)
```js
this.load.spritesheet('hero_run', 'assets/hero_run.png', {
  frameWidth: 32, frameHeight: 32,
  // tuỳ chọn: startFrame, endFrame, margin: 0, spacing: 0
});
```
- Sheet nhiều animation, khung cỡ khác nhau, có xoay/cắt thừa → dùng atlas (Aseprite/TexturePacker xuất JSON hash):
  `this.load.atlas('fx', 'fx.png', 'fx.json')`.
- Một key = một texture; đặt key theo `<thực thể>_<hành động>`.

## Bước 4. Tạo animation một lần, dùng lại
```js
// trong create() của Boot hoặc scene đầu; animation toàn cục, không tạo lại mỗi scene
this.anims.create({
  key: 'hero-run',
  frames: this.anims.generateFrameNumbers('hero_run', { start: 0, end: 7 }),
  frameRate: 12, repeat: -1,
});
const hero = this.add.sprite(160, 90, 'hero_run').play('hero-run');
```
- Atlas: `generateFrameNames('fx', { prefix: 'boom_', start: 0, end: 5, zeroPad: 2 })`.
- Chọn khung cụ thể: `{ frames: [0, 1, 2, 1] }`. `frameRate` mặc định 24, pixel art thường 6-12.
- Hoạt ảnh một lần: `repeat: 0`, nghe `animationcomplete`. Chặn tạo trùng: `if (!this.anims.exists(key))`.
- Hitbox: đặt `body.setSize()/setOffset()` theo phần thân, không theo cả khung.

## Bước 5. Tilemap / tileset (nếu có)
Phóng to hoặc cuộn camera với tileset sát nhau dễ lộ đường kẻ (texture bleeding). Xử lý bằng cách đùn viền tile (extrude) khi xuất tileset, rồi khai `margin: 1, spacing: 2` cho khớp; hoặc giữ zoom nguyên và `pixelArt: true`. Chi tiết xem `reference/tilemaps.md` trong skill gốc.

## Bước 6. Tạo sprite bằng code (khi chưa có art)
Ma trận pixel/palette trong code, vẽ ra canvas rồi `this.textures.addCanvas('key', canvas)`, sau đó dùng như spritesheet bình thường. Giữ palette hữu hạn (8-16 màu), lưu palette ở một chỗ.

## Tiêu chí xong
- [ ] Đã đo từng sheet và phép tính `W/H` khớp công thức Bước 1 (ghi cỡ khung vào comment hoặc `assets/README`).
- [ ] `pixelArt: true`; chạy thử, phóng to không nhoè, không có đường kẻ giữa tile.
- [ ] Mọi animation tạo qua `anims.create` với key rõ ràng; không có `load` trong `create`.
- [ ] Chạy trình duyệt thật, không lỗi console `Texture "x" has no frame "n"`.
- [ ] Asset bên thứ ba: ghi nguồn + giấy phép vào `assets/CREDITS.md`.

## Lỗi hay gặp
| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Hiện nửa nhân vật / nhảy giật | `frameWidth/Height` sai, hoặc bỏ qua `spacing/margin` |
| Mờ khi phóng to | thiếu `pixelArt: true`, hoặc phóng không nguyên |
| Đường kẻ giữa các tile | bleeding: cần extrude hoặc zoom nguyên |
| `anims.create` báo khung không tồn tại | `end` vượt số khung; kiểm `textures.get(key).frameTotal` |
| Animation chạy 2 lần / chồng | tạo lại anim mỗi lần vào scene |
| Sprite bị cắt ở biên | sheet ghép khung không đều → dùng atlas thay vì spritesheet |
