---
name: phaser-khop-xe-nguoi-lai
description: Kiểm tra bằng mắt và bằng số việc người lái (rider) ngồi khớp trên xe (bike/car) trong Phaser 3, gồm thứ tự layer (depth) và pivot/origin khác nhau giữa các sprite. Dùng khi người lái lơ lửng, lệch yên, che sai bánh/tay lái, hoặc khi thêm xe/người lái/skin mới.
---
# Khớp xe + người lái trong Phaser 3

Bổ sung cho `pixel-art-phaser-spritesheet` (đo khung, `pixelArt`). Đọc kỹ năng đó trước nếu sprite còn mờ/lệch khung.

## Mục tiêu
Người lái dính đúng điểm ngồi của xe ở MỌI khung hoạt ảnh và MỌI cặp xe-người, đúng thứ tự che, không rung khi xe nghiêng/nhún.

## Bước 1. Ghi bảng pivot từng asset (đo, không đoán)
Mỗi sprite có origin/pivot khác nhau (xe thường theo bánh sau hoặc tâm thân; người lái theo hông hoặc chân). Lập bảng trong `assets/README` hoặc `data/mount.json`:

| Asset | Cỡ khung | Origin dùng | Ghi chú |
|---|---|---|---|
| bike_a | 64x32 | (0.5, 1) | đáy bánh chạm đất |
| rider_a | 32x32 | (0.5, 1) | pivot ở hông |

Đo điểm gắn bằng ảnh (toạ độ pixel trong khung, gốc trên-trái):
```python
from PIL import Image
im = Image.open("assets/bike_a.png").convert("RGBA"); print(im.size)
# tìm điểm đánh dấu (vd pixel hồng #ff00ff đặt ở yên) nếu art có chừa marker
px = im.load()
print([(x,y) for y in range(im.height) for x in range(im.width) if px[x,y][:3]==(255,0,255)])
```
Mỗi xe khai các điểm: `seat` (hông người lái), `grip` (tay), `foot` (chân/bàn đạp), theo từng khung nếu xe nhún/nghiêng.

## Bước 2. Chọn cách ghép (ưu tiên Container)
```js
// Container: người lái đi theo xe, xoay/nghiêng/lật cùng xe
const bike  = this.add.sprite(0, 0, 'bike_a').setOrigin(0.5, 1);
const rider = this.add.sprite(0, 0, 'rider_a').setOrigin(0.5, 1);
const car = this.add.container(x, y, [bike, rider]);   // thứ tự mảng = thứ tự vẽ
```
- Đặt người lái bằng điểm gắn đổi sang toạ độ cục bộ, có tính origin:
  `localX = seat.x - bike.width*bike.originX`, `localY = seat.y - bike.height*bike.originY`.
  Rồi `rider.setPosition(localX, localY)` (rider origin là hông nên không cộng thêm gì).
- Lật hướng: `car.scaleX = -1` (lật cả container), không lật riêng từng sprite. Pixel art giữ scale nguyên (±1, ±2).
- Không nhét container vào physics; cho body gắn vào `bike` hoặc một zone gốc, container bám theo.

## Bước 3. Thứ tự layer (vẽ từ sau ra trước)
Mẫu thường gặp, ghi rõ lên bảng và dùng chung mọi xe:
1. bóng đổ → 2. bánh/khung xe phía xa → 3. chân xa của người lái → 4. thân xe → 5. thân người lái → 6. chân/tay gần → 7. tay lái + tay gần → 8. hiệu ứng (khói, tia lửa).
- Nếu người lái cần xen giữa xe (chân sau thân xe, tay trước tay lái) thì tách người lái thành 2 sprite (`rider_back`, `rider_front`) hoặc tách xe thành `bike_back/bike_front`.
- Trong Container, thứ tự là thứ tự mảng; đổi bằng `container.moveTo(child, index)`. `setDepth` của con bị bỏ qua so với container, chỉ có `depth` của container so với cảnh ngoài.
- Không ghép: dùng `setDepth` rời nhau và cập nhật mỗi frame theo `y` (sắp xếp theo y); người lái phải `depth = bike.depth + 0.1`, không để hai xe chen giữa.

## Bước 4. Kiểm tra trực quan (bắt buộc, làm được ngay)
Thêm chế độ debug bật bằng phím (vd `D`) hoặc `?debug=1`:
```js
const g = this.add.graphics().setDepth(9999);
function drawDebug(car, bike, rider, pts) {
  g.clear();
  g.lineStyle(1, 0x00ff00).strokeRect(bike.getBounds().x, bike.getBounds().y, bike.getBounds().width, bike.getBounds().height);
  g.lineStyle(1, 0xff0000).strokeRect(rider.getBounds().x, rider.getBounds().y, rider.getBounds().width, rider.getBounds().height);
  const m = car.getWorldTransformMatrix();
  const seat = m.transformPoint(pts.seat.x, pts.seat.y);   // điểm ngồi mong muốn
  g.fillStyle(0xffff00).fillCircle(seat.x, seat.y, 1.5);   // chấm vàng phải trùng hông người lái
}
```
Trang kiểm (scene riêng, `TestFit`): lưới mọi cặp xe x người lái x khung hoạt ảnh (idle, chạy, nghiêng, nhảy), phóng 4x nguyên, nền màu trơn. Chụp màn hình và xem:
- [ ] Chấm `seat` trùng hông; không khe hở, không chồng quá 1px.
- [ ] Chân/tay ở đúng phía (xa/gần) so với thân xe.
- [ ] Qua hết khung hoạt ảnh, người lái không "trượt" (so khung 0 và khung giữa).
- [ ] Lật trái/phải vẫn khớp.
- [ ] Xe nghiêng/nhún: người lái bám theo, không rung.
Kiểm bằng số (tuỳ chọn, chạy được trong test): với mỗi cặp, `|seatWorld - hipWorld| <= 1` pixel.

## Bước 5. Khi thêm xe hoặc người lái mới
Chỉ thêm một dòng dữ liệu (điểm gắn, origin), không sửa code ghép. Chạy lại trang `TestFit` cho cả cặp mới và cặp cũ.

## Tiêu chí xong
- [ ] Bảng pivot/origin + điểm gắn có cho mọi asset và đúng với số đo.
- [ ] Thứ tự layer ghi rõ, dùng chung một nơi.
- [ ] Trang `TestFit` chụp được, mọi cặp qua danh sách ở Bước 4.
- [ ] Chạy trình duyệt thật, console không lỗi.

## Lỗi hay gặp
| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Người lái lơ lửng/chìm cả khối | quên đổi origin: tính vị trí theo góc trên-trái trong khi origin là (0.5,1) |
| Lệch nửa pixel, rung | toạ độ lẻ hoặc scale lẻ; làm tròn và dùng `roundPixels` |
| Lật xe mà người lái lệch | lật riêng sprite thay vì cả container, hoặc điểm gắn không đối xứng |
| `setDepth` trong container không có tác dụng | container sắp theo mảng, dùng `moveTo` |
| Tay che sai tay lái | thiếu tách lớp trước/sau; xem Bước 3 |
| Lệch ở vài khung hoạt ảnh | điểm gắn đo ở một khung; khai điểm gắn theo từng khung |
| Xe mới lệch dù code đúng | khung có viền trong suốt khác nhau; đo lại từ ảnh |
