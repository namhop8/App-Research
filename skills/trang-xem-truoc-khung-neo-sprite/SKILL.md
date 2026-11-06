---
name: trang-xem-truoc-khung-neo-sprite
description: Dựng nhanh một trang HTML/Phaser đứng riêng (không cần vào game) để xem khung (frame/hitbox), điểm neo (origin/anchor) của boss, lính, hố chuột. Dùng khi thêm hoặc đổi sprite/hố và cần kiểm khung có đúng, neo có đúng chỗ chạm đất/miệng hố, trước khi ghép vào màn chơi.
---
# Trang xem trước khung + neo (boss, lính, hố chuột)

Bổ sung cho `pixel-art-phaser-spritesheet` (đo khung, `pixelArt`), `phaser-khop-xe-nguoi-lai` (ghép lớp) và `chup-anh-man-hinh-game` (chụp ảnh). Trang này chỉ để NHÌN và ĐO, không chứa logic game.

## Mục tiêu
Một file `tools/preview.html` mở được ngay: vẽ từng asset phóng nguyên (2x/4x) cùng khung ảnh, khung va chạm, chấm neo, đường đất, và (với hố) vùng miệng hố + vùng che. Nhìn một cái biết lệch hay không.

## Bước 1. Khai dữ liệu một nơi (đo từ ảnh, không đoán)
Dùng một mảng, thêm asset = thêm một dòng. Nếu game đã có file dữ liệu (json/ts) thì đọc đúng file đó để trang không lệch với game.
```js
const ASSETS = [
  // key, file, cỡ khung, số khung, origin (như trong game), hitbox {x,y,w,h} tính từ góc trên-trái khung
  { key:'boss1', url:'assets/boss1.png', fw:96, fh:96, n:6, ox:0.5, oy:1, hit:{x:20,y:10,w:56,h:86}, group:'boss' },
  { key:'linh1', url:'assets/linh1.png', fw:32, fh:32, n:4, ox:0.5, oy:1, hit:{x:6,y:4,w:20,h:28},  group:'linh' },
  // hố chuột: nền hố + lớp che miệng; mouth = hình chữ nhật chuột chui ra
  { key:'ho',    url:'assets/ho.png',    fw:64, fh:48, n:1, ox:0.5, oy:1, hit:null, group:'ho',
    mouth:{x:12,y:14,w:40,h:14}, front:'assets/ho_front.png' },
];
```
Đo kích thước ảnh thật: `python -c "from PIL import Image; print(Image.open('assets/boss1.png').size)"`; `fw*n` phải khớp bề rộng ảnh (hoặc chia hết), nếu không là khai sai.

## Bước 2. Trang mẫu (Phaser qua CDN, hoặc bản Phaser có sẵn trong dự án)
```html
<!doctype html><meta charset="utf-8"><title>Xem trước khung/neo</title>
<body style="margin:0;background:#222"><script src="phaser.min.js"></script><script>
const Z = +new URLSearchParams(location.search).get('z') || 3;   // phóng nguyên
const ASSETS = [/* như Bước 1 */];
class P extends Phaser.Scene {
  preload(){ ASSETS.forEach(a => { this.load.spritesheet(a.key, a.url, {frameWidth:a.fw, frameHeight:a.fh});
                                   if (a.front) this.load.image(a.key+'_front', a.front); }); }
  create(){
    const g = this.add.graphics().setDepth(1000), colW = 120*Z;
    ASSETS.forEach((a,i) => {
      const cx = 20 + i*colW + colW/2, gy = 40 + 110*Z;            // gy = đường đất
      for (let f = 0; f < Math.min(a.n, 3); f++) {                  // xem tối đa 3 khung/asset
        const x = cx, y = gy + f*0;                                 // đổi thành lưới nếu cần
        const s = this.add.sprite(x, gy, a.key, f).setOrigin(a.ox, a.oy).setScale(Z).setVisible(f===0);
        if (f===0) this.vẽ(g, a, s, x, gy);
      }
      this.add.text(cx, gy+8, `${a.key}\n${a.fw}x${a.fh} o(${a.ox},${a.oy})`, {fontSize:'12px',color:'#fff'}).setOrigin(.5,0);
    });
    g.lineStyle(1,0x888888).lineBetween(0, 40+110*Z, 2000, 40+110*Z);
    this.input.keyboard.on('keydown-SPACE', () => this.scene.restart());
  }
  vẽ(g,a,s,x,gy){
    const L = x - a.fw*a.ox*Z, T = gy - a.fh*a.oy*Z;                // góc trên-trái khung trên màn hình
    g.lineStyle(1,0x00ff00).strokeRect(L,T,a.fw*Z,a.fh*Z);          // XANH LÁ: khung ảnh
    if (a.hit) g.lineStyle(1,0xff0000).strokeRect(L+a.hit.x*Z, T+a.hit.y*Z, a.hit.w*Z, a.hit.h*Z); // ĐỎ: hitbox
    if (a.mouth) g.lineStyle(1,0x00ffff).strokeRect(L+a.mouth.x*Z, T+a.mouth.y*Z, a.mouth.w*Z, a.mouth.h*Z); // XANH LƠ: miệng hố
    g.fillStyle(0xffff00).fillCircle(x, gy, 3);                     // VÀNG: điểm neo (origin)
  }
}
new Phaser.Game({type:Phaser.AUTO, width:window.innerWidth, height:600, backgroundColor:'#3a3a3a',
  pixelArt:true, roundPixels:true, scene:P});
</script>
```
Bản trang cho lính/boss nhiều hơn 3 khung: thêm lưới (cột = khung, hàng = asset) thay vì chỉ khung 0. Màu quy ước cố định để ai cũng đọc được: xanh lá = khung, đỏ = hitbox, vàng = neo, xanh lơ = miệng hố.

## Bước 3. Riêng hố chuột
- Ghép đúng thứ tự game dùng: nền hố → chuột (mask hoặc cắt theo `mouth`) → lớp `front` che mép hố. Vẽ chuột ở 2 trạng thái: ẩn hẳn (hoàn toàn dưới `mouth.y`) và nhô hết.
- Neo chuột = chân/đáy thân phải nằm đúng đáy miệng hố khi nhô hết; khi ẩn thì không lộ pixel nào trên mép hố.
- Kéo thanh trượt hoặc phím ↑/↓ đổi `mouth` offset 1px/lần, ghi con số cuối vào dữ liệu Bước 1.

## Bước 4. Chạy và kiểm
1. Phục vụ qua HTTP, không mở `file://`: `python -m http.server 8123` trong thư mục có `preview.html` (chạy nền, xong thì tắt). Mở `http://localhost:8123/tools/preview.html?z=3`.
2. Xem từng asset:
   - [ ] Khung xanh lá ôm sát hình, không cắt mất pixel, không dư viền lớn bất thường.
   - [ ] Chấm vàng nằm đúng chỗ chạm đất (chân boss/lính) hoặc đáy miệng hố.
   - [ ] Hitbox đỏ nằm trong khung và ôm thân, không ôm cả vùng trong suốt.
   - [ ] Mọi khung hoạt ảnh: chân không trượt so với đường đất.
   - [ ] Hố: chuột ẩn không lộ, nhô hết chạm đúng đáy, lớp `front` che đúng.
3. Chụp ảnh bằng script ở `chup-anh-man-hinh-game` (viewport 1280×720, `device_scale_factor=1`), mở ảnh xem thật. Không chạy lệnh được thì thêm ĐÚNG 1 dòng `[CẦN SẾP] cần chạy: python tools/shot.py http://localhost:8123/tools/preview.html?z=3 shots/preview.png 1500`.

## Tiêu chí xong
- [ ] Mọi boss, lính, hố hiện đủ trong trang; dữ liệu khai ở MỘT nơi.
- [ ] Bốn lớp debug (khung, hitbox, neo, miệng hố) đúng màu quy ước.
- [ ] Số đo cuối (origin, hitbox, mouth) đã chép về dữ liệu của game.
- [ ] Console trình duyệt không lỗi; đã tắt server nền.

## Lỗi hay gặp
| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Ảnh hiện nguyên tấm, không cắt khung | `spritesheet` mà khai sai `frameWidth/Height`, hoặc dùng `load.image` |
| Chấm vàng lệch chân dù khung đúng | origin trong trang khác origin trong game; lấy từ cùng dữ liệu |
| Hitbox đỏ lệch khi lật (`scaleX=-1`) | hitbox tính từ góc trái; lật thì phản chiếu `x` quanh tâm neo |
| Mờ, viền răng cưa | thiếu `pixelArt:true`, scale lẻ; dùng `z` nguyên |
| Trang trắng/asset 404 | mở bằng `file://` hoặc sai đường dẫn; dùng HTTP server, xem tab console |
| Khung dư viền trong suốt, hitbox ôm nhầm | đo hitbox theo pixel đặc của ảnh, không theo khung |
| Chuột lộ qua mép hố | thiếu lớp `front` hoặc `mouth.y` thấp hơn mép; chỉnh từng 1px |
