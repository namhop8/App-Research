---
name: xac-thuc-xep-hang-venue
description: Tra cứu và đối soát tự động hạng venue (SCImago SJR Q1 / CORE A*) của từng trích dẫn qua DOI/ISSN bằng API và bảng xếp hạng tải về. Dùng khi cần kiểm chứng hàng loạt danh sách tài liệu trước khi đưa vào paper (bổ trợ cho kiem-chung-trich-dan).
phases: lit, review, writing
---
# Xác thực xếp hạng venue tự động

## Mục tiêu
Từ DOI/arXiv ID → venue thật → hạng (SJR quartile cho tạp chí, CORE cho hội nghị) → kết luận ĐẠT / KHÔNG ĐẠT / CHƯA XÁC MINH. Đạt = Q1 hoặc CORE A* (theo RULES.md mục 3). Mọi kết luận phải có nguồn và năm của bảng xếp hạng.

## Nguồn dữ liệu (ưu tiên miễn phí, không cần khoá)
| Việc | Nguồn |
|---|---|
| Metadata từ DOI (venue, ISSN, năm) | Crossref: `https://api.crossref.org/works/<DOI>` (thêm `mailto=` vào query để vào pool lịch sự) |
| Metadata thay thế | OpenAlex: `https://api.openalex.org/works/doi:<DOI>` → `primary_location.source` (có `issn_l`, `display_name`) |
| arXiv ID | `https://export.arxiv.org/api/query?id_list=<ID>`; nếu có `journal_ref`/DOI thì tra tiếp, nếu không → preprint, KHÔNG tính là đạt |
| Quartile tạp chí | Bảng SCImago (tải CSV từ scimagojr.com, mục Journal Rankings, chọn năm, export CSV; cột `Issn`, `Title`, `SJR Best Quartile`) |
| Hạng hội nghị | Bảng CORE (portal.core.edu.au/conf-ranks, export CSV theo kỳ ICORE/CORE mới nhất; cột Title, Acronym, Rank) |
| Scopus API chính thức (tuỳ chọn) | Cần API key của tổ chức: đọc từ biến môi trường `ELSEVIER_API_KEY`, không ghi vào file/skill/log |

Tải bảng xếp hạng về `lit/rankings/` (thư mục của gemini) kèm tên năm, ví dụ `scimago_2025.csv`, `core_2023.csv`. Ghi năm bảng vào báo cáo; bảng cũ quá 2 năm thì cảnh báo.

## Các bước
1. **Chuẩn hoá đầu vào**: mỗi mục một dòng `khoá, DOI|arXiv, năm`. Bỏ khoảng trắng, hạ chữ thường DOI.
2. **Lấy venue thật** từ Crossref (rồi OpenAlex nếu thiếu). Lưu `container-title`, `ISSN` (chuẩn hoá bỏ dấu `-`), `type` (`journal-article` / `proceedings-article`). Đối chiếu tên bài + năm với bản .bib; lệch → [KHÔNG KHỚP].
3. **Tạp chí**: tra ISSN trong CSV SCImago (cột Issn chứa nhiều ISSN cách nhau dấu phẩy, tách ra so khớp). Lấy `SJR Best Quartile`. Q1 → đạt. Không có ISSN khớp → thử khớp tên đã chuẩn hoá, ghi rõ "khớp theo tên".
4. **Hội nghị**: khớp theo acronym + tên đã chuẩn hoá (bỏ năm, số thứ tự "36th", "Proceedings of"). A* → đạt; A trở xuống → không đạt trừ ngoại lệ hợp lệ (dataset/công cụ/chuẩn) do trưởng nhóm duyệt.
5. **Workshop, preprint, tạp chí săn mồi, không tìm thấy** → [CHƯA XÁC MINH] hoặc KHÔNG ĐẠT, không đoán hạng.
6. **Lưu kết quả** ra `lit/venue_check.csv` và tóm tắt bảng markdown.

## Mẫu mã (Python, 1 thread, có giới hạn tốc độ)
```python
import os, time, requests
os.environ.setdefault("OMP_NUM_THREADS", "2")
H = {"User-Agent": "ResearchLab/1.0 (mailto:<email-phong-nghien-cuu>)"}

def venue_from_doi(doi):
    r = requests.get(f"https://api.crossref.org/works/{doi}", headers=H, timeout=30)
    if r.status_code != 200:
        return None
    m = r.json()["message"]
    return {"venue": (m.get("container-title") or [""])[0],
            "issn": [i.replace("-", "") for i in m.get("ISSN", [])],
            "type": m.get("type"), "title": (m.get("title") or [""])[0]}

# lặp danh sách, time.sleep(0.2) giữa các lần gọi, thử lại tối đa 3 lần khi 429/5xx
```

## Định dạng báo cáo
`khoá | DOI | venue thật | ISSN/acronym | hạng + năm bảng | nguồn | kết luận | ghi chú`

## Tiêu chí xong
- Mọi dòng có kết luận và nguồn; không dòng nào có hạng "đoán".
- Số mục KHÔNG KHỚP / CHƯA XÁC MINH được liệt kê riêng ở đầu báo cáo.
- Đã nêu năm của bảng SCImago và CORE.
- Không có khoá API hay token trong file đầu ra.

## Lỗi hay gặp
- Quartile SCImago theo từng năm và từng category; dùng `Best Quartile`, ghi rõ năm bài xuất bản vs năm bảng.
- Cùng tên khác venue (vd. bản "Letters", "Transactions on X Part B"): khớp ISSN, không khớp tên lỏng.
- DOI của hội nghị đôi khi trỏ về sách LNCS/proceedings series → venue là series, phải tra tên hội nghị thật.
- Crossref trả `container-title` rỗng: chuyển sang OpenAlex.
- Gọi API dồn dập bị 429: giãn cách, cache kết quả vào file để chạy lại không gọi lại.
- Trang SCImago/CORE đổi cấu trúc: tải CSV thủ công qua Thư ký/sếp nếu script không tải được, đừng bỏ qua bước.
