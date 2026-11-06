---
name: tra-doi-chi-doc
description: Tra DOI qua Crossref/OpenAlex chỉ bằng công cụ đọc/tải trang (GET URL), không chạy lệnh, để kiểm venue thật và nội dung câu cite. Dùng khi phiên bị khoá terminal/ghi file mà vẫn phải xác minh trích dẫn (bản nhẹ của xac-thuc-xep-hang-venue).
phases: lit, review, writing
---
# Tra DOI chỉ đọc (Crossref / OpenAlex)

## Mục tiêu
Với mỗi `\cite`, xác nhận DOI/arXiv trỏ đúng bài (tên, tác giả, năm), lấy venue thật, và đối chiếu với câu dẫn, mà KHÔNG chạy python/curl, KHÔNG ghi file. Kết quả là bảng trong báo cáo. Hạng venue (Q1/A*) vẫn phải có bảng SCImago/CORE; không có thì ghi [CHƯA XÁC MINH HẠNG], không đoán.

## Công cụ được dùng
- Công cụ tải trang web / fetch URL (chỉ GET) nếu phiên có. Công cụ đọc file (`Read`, `Grep`) để xem `.bib`, `.tex`, `lit/rankings/*.csv`.
- Nếu phiên không có công cụ tải URL: làm phần đối chiếu `.bib` ↔ `.tex` được, rồi kết thúc báo cáo bằng `[CẦN SẾP] <cho phép công cụ tải URL / nhờ Thư ký chạy tools tra DOI>`. Không bịa metadata từ trí nhớ.

## URL mẫu (không cần khoá)
| Việc | URL |
|---|---|
| Crossref theo DOI | `https://api.crossref.org/works/<DOI>?mailto=<email-phòng>` |
| Chỉ lấy vài trường | `https://api.crossref.org/works/<DOI>?select=title,container-title,ISSN,type,issued,author,abstract` |
| OpenAlex theo DOI | `https://api.openalex.org/works/doi:<DOI>?select=title,publication_year,primary_location,authorships,abstract_inverted_index,type` |
| Tìm DOI theo tên bài | `https://api.crossref.org/works?query.bibliographic=<tên+bài+tác+giả+năm>&rows=3&select=DOI,title,container-title,issued` |
| arXiv | `https://export.arxiv.org/api/query?id_list=<ID>` (xem `journal_ref`, `doi`) |

DOI phải mã hoá URL (`/` giữ nguyên, `<`, `>`, `;`, `(`, `)` mã hoá). Dùng chữ thường khi so sánh.

## Các bước
1. Gom danh sách `khoá | DOI/arXiv | năm | câu dẫn` từ `.bib`/`.tex` (dùng `Grep` tìm `\cite{`).
2. Mỗi DOI: tải Crossref; trống `container-title` hoặc 404 → thử OpenAlex; vẫn không có → thử tìm theo tên bài; vẫn không có → [CHƯA XÁC MINH].
3. So khớp với `.bib`: tên bài, tác giả đầu, năm, venue. Lệch bất kỳ → [KHÔNG KHỚP] và nêu cụ thể lệch gì.
4. Venue: `container-title`, `ISSN`, `type` (`journal-article` / `proceedings-article`). arXiv không có `journal_ref`/DOI → preprint, không tính đạt chuẩn.
5. Hạng: nếu có `lit/rankings/scimago_<năm>.csv` / `core_<năm>.csv` thì `Grep` ISSN (bỏ dấu `-`) hoặc acronym; ghi năm bảng. Không có bảng → để trống hạng, ghi lý do.
6. Nội dung câu cite: đọc abstract (Crossref `abstract` hoặc OpenAlex `abstract_inverted_index`, ghép lại theo vị trí). Câu dẫn có số liệu, so sánh, "state-of-the-art", "first" mà abstract không nêu → [CẦN ĐỌC BẢN ĐẦY ĐỦ], không kết luận đúng. Abstract chỉ đủ xác nhận chủ đề, không đủ xác nhận số cụ thể.
7. Báo cáo theo bảng của `kiem-chung-trich-dan`, thêm cột nguồn (URL đã gọi).

## Định dạng kết quả
`khoá | DOI | tên bài thật | venue thật + ISSN | type | hạng + năm bảng | khớp .bib? | câu dẫn khớp abstract? | ghi chú`

## Tiêu chí xong
- Mỗi dòng có URL nguồn thật đã tải; dòng nào không tải được ghi rõ [CHƯA XÁC MINH].
- Không có hạng nào lấy từ trí nhớ.
- Phần KHÔNG KHỚP / CHƯA XÁC MINH liệt kê riêng ở đầu báo cáo.
- Không ghi file, không chạy lệnh; không đưa khoá/token vào báo cáo.

## Lỗi hay gặp
- DOI sai ký tự cuối (dấu chấm, ngoặc) khi copy từ PDF: bỏ ký tự thừa rồi thử lại.
- DOI của hội nghị trỏ về series LNCS/proceedings: venue thật là hội nghị, tra thêm tên đó.
- Crossref `abstract` thường là JATS XML hoặc thiếu; ưu tiên OpenAlex khi thiếu.
- Một tên bài có cả bản arXiv lẫn bản tạp chí: cite bản đã xuất bản, kiểm DOI bản đó.
- Tìm theo tên cho kết quả đầu tiên không chắc đúng: so cả năm và tác giả, không nhận khi chỉ khớp một phần.
- API trả 429: giãn cách, gọi ít trường bằng `select`, tra ưu tiên các câu cite mang tải chính trước.
