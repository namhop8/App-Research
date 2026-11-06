---
name: ghep-lop-paper-doll-chibi
description: Ghép lớp nhân vật paper-doll chibi 56x88 (thân, mặt, tóc, 10 ô đồ; 4 hướng x đứng/đi/chạy) cho Khoa, Linh, Bảo, và thêm kiểu tóc/áo/mũ mới (đuôi ngựa, tóc rối, nón lưỡi trai ngược) vào `avatar_style.chibi`. Dùng khi Phòng Game thêm kiểu mới, đồ lệch neo, hoặc lớp che sai thứ tự ở một hướng.
---
# Ghép lớp paper-doll chibi (neo thân 56x88)

Bổ sung cho `ve-nhan-vien-ngoi-ban-chibi` (nhân viên NGỒI bàn, 4 khung gõ) và `pixel-art-phaser-spritesheet` (nạp/cắt khung). Kỹ năng này lo nhân vật ĐỨNG/ĐI/CHẠY ghép từ nhiều lớp.

Lưu ý nguồn: viết khi chưa đọc được mã `E:\CTFCLANWAR` (ngoài quyền). Tên ô đồ, thứ tự hàng, tên khoá trong `avatar_style.chibi` dưới đây là MẶC ĐỊNH đề xuất; trước khi làm phải đối chiếu `content/wardrobe.json` và `tools/char_wardrobe_av.py`, lệch thì theo mã thật.

## Mục tiêu
Mỗi lớp là một sheet riêng cùng lưới khung 56x88, cùng neo thân, xếp chồng theo thứ tự cố định ĐỔI THEO HƯỚNG. Thêm một kiểu tóc/áo/mũ = thêm dữ liệu + 1 sheet lớp, không sửa hàm ghép.

## Quy ước lưới (đo lại bằng `Image.size`)
- Khung 56x88, nền trong suốt, không margin/spacing. Chân chạm y=87, `setOrigin(0.5, 1)`.
- Hàng = hướng: `0 xuống, 1 trái, 2 phải, 3 lên`. Cột = hoạt ảnh: `idle` 2 khung, `walk` 4, `run` 6 (tổng 12 cột -> sheet 672x352). Nếu game đã dùng số khung khác thì theo game, chỉ ghi cho nhất quán.
- Phải = lật ngang của trái CHỈ KHI lớp đối xứng. Đuôi ngựa buộc lệch bên, logo chữ trên áo, nón ngược có khoá sau: vẽ riêng hàng phải hoặc lật xong sửa tay.

## Neo thân (cố định, mọi lớp dùng chung)
Toạ độ trong khung 56x88 (x, y, rộng, cao); đối chiếu bố cục đầu chibi ở kỹ năng ngồi bàn.
| Neo | Vùng | Ghi chú |
|---|---|---|
| `head` | 14, 4, 28, 24 | đầu ≈ 1/3 chiều cao |
| `face` | mắt tại y 16, hai ô 3x4 cách 8 px | hướng lên: không vẽ mặt |
| `torso` | 18, 28, 20, 18 | áo, ba lô, áo khoác |
| `arms` | 4x10 hai bên thân | đung đưa ngược chân khi đi/chạy |
| `legs` | 18..38, y 46..87 | quần, giày |
Dịch chuyển theo khung (bob đầu 1 px, chân luân phiên 2-3 px, chạy nghiêng thân 1 px) áp lên TOÀN BỘ lớp cùng một giá trị `dx,dy` của khung đó, lấy từ một bảng `POSE[anim][frame]`, không để mỗi lớp tự tính.

## Thứ tự lớp (dưới -> trên), đổi theo hướng
| Hướng | Thứ tự |
|---|---|
| xuống | `hair_back, body, legs_item, torso_item, face, hair_front, hat, held` |
| trái / phải | `hair_back(đuôi ngựa), body, legs_item, torso_item, face, hair_front, hat, held` (tay xa vẽ trước thân) |
| lên | `body, legs_item, torso_item, hair_back+hair_front (che gáy), hat, held` (không có `face`) |
10 ô đồ: lấy đúng tên và thứ tự từ `content/wardrobe.json`, gán MỖI ô vào một tầng ở bảng trên (đầu: mũ/kính/tai nghe; thân: áo/áo khoác/ba lô; chân: quần/giày; tay: vật cầm/hiệu ứng). Ghi bảng gán ô -> tầng vào `assets/README` để không đoán lại.

## Thêm kiểu mới (dữ liệu, không code)
Mở rộng `avatar_style.chibi`, ví dụ (tên khoá theo mã thật):
```json
{ "hair": ["bob", "short", "ponytail", "messy"],
  "top":  ["hoodie", "jacket"],
  "hat":  ["none", "cap_back"] }
```
Mỗi kiểu cần đủ lớp theo hướng:
| Kiểu | Lớp cần | Chú ý theo hướng |
|---|---|---|
| `ponytail` | `hair_front` (mái + đỉnh) và `hair_back` (đuôi) | xuống: đuôi lòi 2-3 px hai bên cổ hoặc không thấy; bên: đuôi sau gáy, đu đưa 1-2 px ngược nhịp bước (chạy 3 px); lên: đuôi che gáy, ở trên thân |
| `messy` | `hair_front` với 3-5 lọn nhô lệch, `hair_back` ngắn | bóng tóc rộng hơn đầu 1-2 px mỗi bên; không đối xứng, vẽ cả hàng phải |
| `cap_back` (nón lưỡi trai ngược) | `hat` | xuống: thấy mặt sau nón (dây điều chỉnh/khe hở) trên trán, không có lưỡi; bên: lưỡi chìa RA SAU gáy; lên: lưỡi chìa về phía người xem, đè lên tóc gáy. Nón nằm trên `hair_front`, tóc `hair_back` vẫn lộ dưới vành |
Màu tóc/áo/nón là palette tham số hoá (tô theo dict), đừng nướng màu vào sheet để Khoa/Linh/Bảo dùng chung hình dạng.

## Bước làm
1. Đọc `content/wardrobe.json`, `char_wardrobe_av.py`; chốt bảng 10 ô -> tầng, số khung, bảng `POSE`.
2. Vẽ lớp mới trên cùng lưới, mỗi lớp một PNG `assets/chars/<lop>/<kieu>.png`, viền tối 1 px, không antialias.
3. Ghép bằng hàm dưới, xuất `_preview` phóng 3x NEAREST cho cả 3 nhân vật x 4 hướng x 3 hoạt ảnh.
4. Xem preview bằng công cụ đọc ảnh: kiểm từng hướng, xếp cạnh nhau một hàng "mix 10 ô đồ" để phát hiện đồ đè nhau.

## Mẫu ghép (Pillow)
```python
from PIL import Image
W, H = 56, 88
ORDER = {  # tầng dưới -> trên theo hướng
  "down":  ["hair_back","body","legs","torso","face","hair_front","hat","held"],
  "side":  ["hair_back","body","legs","torso","face","hair_front","hat","held"],
  "up":    ["body","legs","torso","hair_back","hair_front","hat","held"],
}
def lop(ten, kieu, hang, cot):             # cắt 1 khung từ sheet lớp
    s = Image.open(f"assets/chars/{ten}/{kieu}.png").convert("RGBA")
    return s.crop((cot*W, hang*H, (cot+1)*W, (hang+1)*H))
def ghep(chon, huong, hang, cot, dx=0, dy=0):
    out = Image.new("RGBA", (W, H), (0,0,0,0))
    for ten in ORDER[huong]:
        if ten in chon and chon[ten] != "none":
            out.alpha_composite(lop(ten, chon[ten], hang, cot), (dx, dy))
    return out
```
Chạy một lần trước khi tin: mẫu chưa chạy thử.

## Tiêu chí xong
- [ ] Mọi sheet lớp cùng cỡ (672x352 hoặc theo game), `Image.size` đúng; đáy nhân vật y=87.
- [ ] Mỗi kiểu mới có đủ 4 hướng x 3 hoạt ảnh; hướng lên không lộ mặt.
- [ ] 3 nhân vật x kiểu tóc mới x nón ngược xem ở 1x vẫn đọc rõ; nón không đè mắt, tóc không đâm xuyên nón.
- [ ] Ảnh "mix 10 ô đồ" không có lớp sai thứ tự hay lỗ hổng da.
- [ ] Trong Phaser: các lớp chạy cùng frame index một lúc (không lệch nhịp), không lỗi `has no frame`.
- [ ] `avatar_style.chibi` và `wardrobe.json` cập nhật khớp; kiểu cũ (`bob`, `short`, `hoodie`, `jacket`) vẫn ra y hệt.

## Lỗi hay gặp
| Triệu chứng | Cách xử |
|---|---|
| Đồ trôi khỏi thân khi đi/chạy | mỗi lớp tự tính dịch; dùng chung `POSE` |
| Đuôi ngựa nằm trước mặt ở hướng bên | `hair_back` phải dưới `body` |
| Nón ngược lộ lưỡi ở hướng xuống | lưỡi chỉ vẽ ở hướng bên (ra sau) và hướng lên |
| Hàng phải trông sai (đuôi lệch bên sai) | lớp bất đối xứng không được lật máy móc |
| Viền sáng/răng cưa quanh lớp | `alpha_composite`, không `paste` không mặt nạ; lưu RGBA, không `convert("P")` |
| Thêm kiểu nhưng game vẫn chỉ ra 2 | chưa thêm tên vào enum/schema của `avatar_style.chibi` và danh mục wardrobe |
