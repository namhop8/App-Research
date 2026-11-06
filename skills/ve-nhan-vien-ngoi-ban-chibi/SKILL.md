---
name: ve-nhan-vien-ngoi-ban-chibi
description: Vẽ sprite nhân viên chibi 56x88 ngồi ở bàn gõ phím (spritesheet 4 khung) bằng Python/Pillow, để đặt vào phòng SOC, Mèo Code và các phòng khác của văn phòng game. Dùng khi Phòng Game cần thêm nhân viên ngồi bàn, đổi áo/tóc/phụ kiện theo phòng, hoặc sprite ngồi bị lệch/mờ.
---
# Vẽ nhân viên ngồi bàn gõ phím (chibi 56x88)

Kỹ năng này lo phần VẼ. Phần nạp vào Phaser (cắt khung, `pixelArt`, anim) xem `pixel-art-phaser-spritesheet`.

## Mục tiêu
Một sheet `assets/staff_<vaitro>_type.png` cỡ 224x88 (4 khung 56x88, ngang, không margin/spacing), nền trong suốt, nhân vật ngồi quay mặt ra người xem, hai tay trên bàn phím, gõ lặp.

## Bố cục lưới 56x88 (toạ độ pixel, gốc trái-trên)
| Phần | Vùng (x, y, rộng, cao) | Ghi chú |
|---|---|---|
| Đầu chibi | 14, 4, 28, 24 | đầu ≈ 1/3 chiều cao: nét chibi |
| Tóc/mũ/tai mèo | phủ trên đầu, y 2..12 | phụ kiện theo phòng |
| Mắt | 2 ô 3x4 tại y 16 | cách nhau 8 px, to và thấp |
| Thân (áo) | 18, 28, 20, 18 | |
| Tay | cánh tay 4x10 hai bên, bàn tay 4x3 chạm phím | khung gõ đổi tay nhấc lên |
| Bàn | 0, 56, 56, 6 (mặt bàn) + 2, 62, 4, 26 và 50, 62, 4, 26 (chân) | che nửa dưới thân |
| Bàn phím | 12, 52, 32, 4 | nằm trên mặt bàn |
| Chân/ghế | chân 18..38, y 66..84; ghế lộ hai bên | dưới bàn, tối hơn |
Chân sprite chạm đáy (y = 87) để đặt vào phòng theo `setOrigin(0.5, 1)`.

## Bước làm
1. Chốt palette 12-16 màu ở MỘT chỗ (dict đầu file): da, tóc, áo, áo-tối, viền, bàn, bàn-tối, phím, mắt, phụ kiện. Dùng viền 1 px màu tối cho toàn thân để nổi trên nền phòng.
2. Viết hàm vẽ theo khung bằng chữ nhật (không dùng antialias, không resize bằng nội suy).
3. Xuất 4 khung: 0 tay trái xuống, 1 cả hai xuống, 2 tay phải xuống, 3 cả hai xuống; đầu nhúc nhích 1 px ở khung 1 và 3 cho sống động.
4. Ghép sheet, lưu PNG, kiểm bằng ảnh phóng 4x nguyên (NEAREST) rồi nhìn bằng công cụ đọc ảnh.

## Mẫu code (chạy `python tools/ve_nhan_vien.py soc`)
```python
from PIL import Image, ImageDraw
W, H, N = 56, 88, 4
P = dict(da=(255,214,170), mat=(30,30,50), vien=(35,30,50),
         ban=(150,105,70), ban_t=(110,75,50), phim=(70,75,90),
         chan=(50,55,80), ghe=(60,60,70))
VAITRO = {  # đổi theo phòng
  "soc":  dict(toc=(40,40,60),  ao=(40,110,200), ao_t=(25,75,150), phu="tai_nghe"),
  "meo":  dict(toc=(230,150,60), ao=(120,200,120), ao_t=(80,150,85), phu="tai_meo"),
}
def r(d, x, y, w, h, c): d.rectangle([x, y, x+w-1, y+h-1], fill=c+(255,))
def khung(v, i):
    im = Image.new("RGBA", (W, H), (0,0,0,0)); d = ImageDraw.Draw(im)
    dy = 1 if i in (1, 3) else 0                       # đầu nhúc nhích
    r(d,16,60,24,26,P["chan"]); r(d,10,48,4,16,P["ghe"]); r(d,42,48,4,16,P["ghe"])
    r(d,17,28+dy,22,20,P["vien"]); r(d,18,29+dy,20,18,v["ao"]); r(d,18,40+dy,20,7,v["ao_t"])
    r(d,13,4+dy,30,26,P["vien"]); r(d,14,5+dy,28,24,P["da"])      # đầu
    r(d,14,5+dy,28,8,v["toc"]); r(d,14,12+dy,3,8,v["toc"]); r(d,39,12+dy,3,8,v["toc"])
    r(d,19,16+dy,3,5,P["mat"]); r(d,34,16+dy,3,5,P["mat"])         # mắt
    if v["phu"] == "tai_meo":
        for x in (14, 34): r(d,x,0+dy,8,6,v["toc"])
    else:
        r(d,12,12+dy,3,9,(200,200,210)); r(d,41,12+dy,3,9,(200,200,210)); r(d,15,3+dy,26,2,(200,200,210))
    l = 0 if i in (0, 1) else 3; rr = 0 if i in (2, 1) else 3         # tay nhấc/hạ
    r(d,14,38,5,14-l,P["da"]); r(d,37,38,5,14-rr,P["da"])
    r(d,0,56,56,6,P["ban"]); r(d,0,60,56,2,P["ban_t"])
    r(d,12,52,32,4,P["phim"])
    r(d,14,50-l,5,3,P["da"]); r(d,37,50-rr,5,3,P["da"])
    r(d,2,62,4,26,P["ban_t"]); r(d,50,62,4,26,P["ban_t"])
    return im
def main(ten):
    v = VAITRO[ten]; sheet = Image.new("RGBA", (W*N, H), (0,0,0,0))
    for i in range(N): sheet.paste(khung(v, i), (i*W, 0))
    sheet.save(f"assets/staff_{ten}_type.png")
    sheet.resize((W*N*4, H*4), Image.NEAREST).save(f"assets/_preview_{ten}.png")
if __name__ == "__main__":
    import sys; main(sys.argv[1])
```
Đây là khung xương để chỉnh mắt nhìn, không phải bản cuối: sau khi xem preview, dịch/tô lại vài ô cho đẹp (thân, tay, ghế) rồi mới chốt. Mẫu chưa được chạy thử trong lượt này (chế độ không chạy lệnh), nên lần đầu cần chạy và xem preview.

## Nạp vào Phaser
```js
this.load.spritesheet('staff_soc', 'assets/staff_soc_type.png', { frameWidth: 56, frameHeight: 88 });
this.anims.create({ key: 'soc-type', frames: this.anims.generateFrameNumbers('staff_soc', { start: 0, end: 3 }),
                    frameRate: 8, repeat: -1 });
this.add.sprite(x, y, 'staff_soc').setOrigin(0.5, 1).play('soc-type');
```
- `x, y` là số nguyên; muốn to hơn thì `setScale` số nguyên (2, 3), `pixelArt: true` trong config.
- Thêm nhân viên mới = thêm một mục trong `VAITRO` (màu áo, tóc, phụ kiện), không sao chép hàm vẽ.
- Phân biệt theo phòng: SOC = tai nghe + áo xanh; Mèo Code = tai mèo + áo xanh lá. Màu áo khác nhau rõ ở 1x.

## Tiêu chí xong
- [ ] Sheet đúng 224x88, nền trong suốt; `Image.open(...).size` in ra `(224, 88)`.
- [ ] Xem `_preview` thấy rõ: đầu to, mắt, áo, tay chạm phím, bàn che nửa thân dưới.
- [ ] 4 khung khác nhau ở tay; đầu không lệch quá 1 px; chân sprite chạm y=87.
- [ ] Đọc rõ ở kích thước 1x trên nền phòng tối lẫn sáng (nhờ viền).
- [ ] Trong game không mờ, không nhảy khung; không có lỗi console `has no frame`.
- [ ] Mỗi phòng nhìn khác nhau ngay (màu áo/phụ kiện).

## Lỗi hay gặp
| Triệu chứng | Cách xử |
|---|---|
| Sprite mờ khi phóng | dùng `Image.NEAREST`, phóng nguyên, `pixelArt: true` |
| Nhân vật "lơ lửng" trên sàn | đáy khung không chạm y=87 hoặc quên `setOrigin(0.5, 1)` |
| Gõ trông giật | đổi tay quá nhiều px; chỉ nhấc 3 px, 8 khung/giây |
| Nhân vật chìm vào nền | thiếu viền tối 1 px quanh thân |
| Màu trôi khi lưu | lưu PNG RGBA, không JPEG; không dùng `convert("P")` |
| Hai phòng giống nhau | thêm phụ kiện đặc trưng, không chỉ đổi sắc độ |
