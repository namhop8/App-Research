# Prompt: dựng "Văn phòng AI" quản lý nhiều nhân viên AI (Claude Code, Antigravity, Gemini…)

> Dán toàn bộ phần dưới vào Claude Code (hoặc AI lập trình tương tự), chạy trong một thư mục trống. Nên làm theo từng giai đoạn, kiểm tra xong mới sang giai đoạn sau.

---

Bạn là kỹ sư phần mềm. Hãy dựng cho tôi một **"văn phòng AI"**: một app chạy trên máy (Windows), trong đó nhiều trợ lý AI là **nhân viên** có phòng ban, cấp bậc, nhận việc qua hộp thư, tự làm, được duyệt nhiều cấp rồi trình sếp (là tôi) ký. Giao diện dễ thương hoặc kiểu hacker, mỗi nhân viên là một nhân vật ngồi ở bàn.

## 1. Kỹ thuật bắt buộc

- **Backend:** Python 3, **chỉ dùng thư viện chuẩn** (http.server, json, subprocess, threading, ctypes). Không cài thêm gói nào.
- **Frontend:** một file `app/index.html` duy nhất (HTML + CSS + JS thuần), không build, không framework.
- **Dữ liệu:** file JSON trong `state/` (office.json, activity.jsonl, secrets.json). Ghi file nguyên tử (ghi file tạm rồi `os.replace`), có khoá dùng chung giữa nhiều tiến trình.
- **Server** chỉ nghe `127.0.0.1`; chặn request có `Host`/`Origin` lạ (chống DNS rebinding); POST bắt buộc `Content-Type: application/json`.
- **Mở app:** chạy bằng `pythonw` (không hiện cửa sổ đen), tự mở trình duyệt; có nút ⏻ tắt văn phòng trong app; lần đầu chạy tự tạo shortcut Desktop.
- **Không đường dẫn cứng:** mọi đường dẫn tính từ thư mục gốc của app, để chép cả thư mục sang máy khác vẫn chạy.

## 2. Nhân viên = nhà cung cấp AI

Mỗi nhân viên có: tên (sếp đặt cho vui), chức danh, phòng, màu, phụ kiện, **vai trò** (một đoạn mô tả cách làm việc, được đưa vào lời dặn mỗi lần làm), nhà cung cấp, model, cờ "tự nhận thư".

Nhà cung cấp (khai báo dạng bảng `PRESETS`, thêm loại mới không phải sửa giao diện):

| Loại | Cách gọi chạy nền |
|---|---|
| Claude Code CLI | `claude -p --output-format stream-json --verbose --include-partial-messages --permission-mode plan` (chỉ đọc) / `acceptEdits` (được sửa) |
| Antigravity CLI (`agy`, cài bằng `winget install Google.AntigravityCLI`) | `agy -p "<lời dặn>" --mode plan --output-format stream-json --add-dir <thư mục>` |
| Codex CLI, Gemini CLI | tương tự |
| API kiểu OpenAI (Gemini API, OpenRouter, Ollama, MiMo…) | POST `/chat/completions` bằng urllib |
| Tự báo cáo | app khác, tự chấm công bằng lệnh CLI của văn phòng |

Trong hồ sơ nhân viên có các nút: ⬇️ Cài đặt, 🔑 Đăng nhập (mở cửa sổ terminal để **người dùng tự** đăng nhập), 🗝️ Nhập API key (lưu riêng, app không bao giờ hiện lại, không đóng gói khi chia sẻ), 🩺 Kiểm tra kết nối, chọn model (danh sách lấy từ CLI/API nếu có).

## 3. Những lỗi phải tránh (đã gặp thật)

1. **Windows + file `.cmd`** (claude.cmd, gemini.cmd chạy qua cmd.exe): cmd **cắt tham số ở chỗ xuống dòng**, nên mất hết các cờ phía sau. Không bao giờ đưa lời dặn nhiều dòng qua tham số; đưa qua **stdin**.
2. **Antigravity:** `--disable-slash-commands` làm `--mode plan` **mất tác dụng**, khiến mọi thao tác cần xin phép (kể cả đọc file) bị tự chặn khi chạy nền. Đừng dùng cờ đó với agy.
3. **Antigravity không tự cho đọc thư mục đang đứng:** luôn `--add-dir` thư mục app, thư mục dữ liệu của việc, và thư mục mà lệnh của sếp nhắc tới (tự dò đường dẫn kiểu `D:\...` trong lệnh). Cho tiến trình đứng ở **thư mục dữ liệu của việc** để đường dẫn tương đối trỏ đúng.
4. **Gemini CLI đăng nhập tài khoản Google cá nhân** đã bị Google chặn ("IneligibleTier… migrate to Antigravity"): dùng Antigravity CLI hoặc Gemini API key thay thế.
5. **PATH cũ:** app mở từ Explorer có PATH từ trước khi cài Node, nên phải tự dò `%APPDATA%\npm`, `C:\Program Files\nodejs`, `%LOCALAPPDATA%\Microsoft\WinGet\Links` và `...\WinGet\Packages\*\agy.exe`.
6. **Tiết kiệm token với Claude Code:** chỉ cấp công cụ cần dùng (`--tools Read,Glob,Grep`, thêm `Edit,Write` khi được sửa, `Bash` khi phòng cho phép) cùng `--disable-slash-commands --strict-mcp-config --setting-sources project`. Mỗi lần gọi giảm từ khoảng 47K xuống khoảng 7,5K token. **Không dùng `--bare`** (mất đăng nhập).
7. **Prompt cache:** tách phần cố định (nội quy, quy tắc, vai trò, kỹ năng) vào `--append-system-prompt-file` (file đặt tên theo hash nội dung). Phần thay đổi (thư, tài liệu) để cuối. Lần gọi sau rẻ hơn khoảng 5 lần.
8. **Đừng tự khởi động lại server khi có nhân viên đang chạy;** chờ rảnh. Khi đóng một việc thì **dừng ngay** tiến trình đang làm việc đó (giữ danh sách tiến trình đang chạy) và huỷ thư còn chờ của việc đó.
9. **Thư cùng tên trong cùng giây** sẽ ghi đè nhau: thêm hậu tố `-2`, `-3`. Thư hỏi sếp đã trả lời hoặc bỏ qua phải đổi thành `.done.md`, nếu không mũi tên luồng trên bản đồ sẽ còn mãi.
10. **Nhân viên bị chặn bởi thứ chỉ sếp quyết được** (quyền, dữ liệu, tiêu chí bất khả thi) sẽ nộp thiếu, bị trả lại, quay vòng và đốt quota. Bắt buộc có cơ chế **"[CẦN SẾP]"** (mục 5).
11. **Lệnh cần ghi file mà chạy chỉ đọc sẽ lặp** (hỏi quyền → từ chối → gửi lại y cũ → hỏi lại). Loại việc cần ghi (vd tạo đề) tự chạy chế độ ghi; sếp từ chối [CẦN SẾP] mà không ghi chỉ đạo thì **dừng việc**; cấp quyền phải bằng nút (đổi chế độ chạy thật), không bằng chữ.
12. **Vòng "làm lại cho tới khi đạt" phải có giới hạn cứng trong code** (đếm số lần trượt, quá 3 lần thì chặn và hỏi sếp), không chỉ dặn trong lời nhắc.
13. **Phòng hệ thống trong ô chọn phòng:** hồ sơ nhân viên phải luôn liệt kê phòng hiện tại của người đó, nếu không bấm Lưu sẽ chuyển người đó đi.

## 4. Hộp thư và tự làm việc

- Giao việc = file Markdown trong `inbox/` có phần đầu YAML (from, to, kind, subject, mode read|write, workdir, task, stage…).
- Một luồng nền dò hộp thư mỗi 5 giây. Mỗi nhân viên tự động làm thư của mình (mỗi người một luồng), ghi kết quả vào `outputs/<nhân viên>/`, đổi thư thành `.done.md`.
- `mode: write` thì phải xin duyệt trước (mục 6).
- Đọc **luồng sự kiện** (stream-json) để biết **từng thao tác** ("📖 Đọc main.tex", "🔍 Tìm…", "✍️ Sửa…") và **chữ đang nghĩ / đang viết**, đồng thời đọc **số token thật** và **hạn mức thật** (Claude có `rate_limit_event.unifiedWindows` cho cửa sổ 5 giờ và 7 ngày).
- Hết quota thì nhân viên **đi ngủ** tới giờ reset rồi tự dậy làm tiếp.
- Mọi báo cáo phải mở đầu bằng `## Tóm tắt` (tối đa 5 dòng).

## 5. Quy trình cấp bậc (bật theo phòng)

`Sếp ra lệnh → Trưởng phòng chia việc ("[GIAO @Tên] …") → Nhân viên làm → Trưởng phòng duyệt lần 1 → Phó sếp duyệt lần 2 → Sếp ký`

- Người duyệt kết thúc bằng `[DUYỆT] …`, `[CHƯA ĐẠT] <vấn đề đánh số + cách sửa>` hoặc `[CẦN SẾP] <câu hỏi + phương án>`.
- Chưa đạt thì trả về người làm, kèm vấn đề và kết quả lần trước. Tối đa 2 lần, quá thì trình sếp quyết.
- `[CẦN SẾP]` (người làm hay người duyệt đều dùng được) thì việc **dừng lại**, câu hỏi hiện ở mục "Chờ sếp"; sếp trả lời xong việc tự chạy tiếp, không tính là bị trả lại.
- Mức quy trình chọn được khi ra lệnh: ⚡ Nhanh (làm → sếp), 🔎 Chuẩn (→ trưởng phòng → sếp), 🏛️ Đầy đủ.
- Trưởng phòng vắng (chưa đăng nhập, lỗi, hết token) thì người dùng được trong phòng **tạm quyền**.
- Tiết kiệm: trưởng phòng duyệt bằng model nhẹ; Phó sếp chỉ dùng model mạnh cho việc nặng (viết, code, deploy, bảo mật); kết quả dài thì Phó sếp đọc tóm tắt kèm dàn ý; việc nhẹ (tìm tài liệu, ý tưởng) bỏ qua Phó sếp.

## 6. Quầy lễ tân

- **Thư ký:** gom mọi yêu cầu xin duyệt (quyền sửa file, chạy lệnh, đăng nhập, ký, câu hỏi [CẦN SẾP]). Có chuông và thông báo trình duyệt.
- **Phó sếp:** giữ **lệnh thường trực** của sếp (ví dụ "cứ deploy hết đi" cho phòng X) và duyệt thay khi khớp. **Không bao giờ duyệt thay** lệnh nguy hiểm (`rm -rf`, `prune`, `push --force`, `DROP TABLE`, `reset --hard`…) và việc đăng nhập.
- **Sổ nội quy của sếp:** các yêu cầu chung, luôn đặt đầu lời dặn của mọi nhân viên.
- **Phòng Kỹ năng:** nhân viên ghi `[CẦN KỸ NĂNG] …` thì văn phòng nhờ thợ kỹ năng viết `skills/<tên>/SKILL.md` (có `phases:` để chỉ đưa vào loại việc phù hợp), xong tự gắn vào phòng đã nhờ. Chặn nhờ trùng.

## 7. Giao diện

- **Tổng quan 3D isometric:** mỗi phòng là một ô sàn, mọi phòng nằm trong một màn hình (tự co giãn), kéo để xoay, cuộn để phóng to, bấm đúp để về mặc định.
- **Mũi tên luồng việc** có chấm sáng chạy từ A tới B, mỗi loại luồng một màu (giao việc, nộp duyệt, trình Phó sếp, trả lại, xin duyệt, nhờ kỹ năng), có chú thích. Toạ độ phải chia cho hệ số phóng của giao diện.
- **Nhân vật:** tên model đang chạy hiện trên đầu (cùng cỡ chữ với tên); **bong bóng suy nghĩ chữ chạy** (thao tác + chữ đang nghĩ); vầng sáng màu; **thanh máu** = hạn mức (số thật nếu có, không thì ước tính) và giờ hồi; thanh tuần.
- **Mục "🔴 Đang làm":** mỗi người đang làm một thẻ: việc đầy đủ, thao tác hiện tại cùng vài thao tác trước, thời gian đã làm.
- **Nút trên đầu:** ⏳ Chờ sếp (đếm số; duyệt/ký, câu hỏi của nhân viên kèm ô trả lời gửi thẳng về người hỏi, kết quả chờ xem), 🛠️ Sự cố (tự dò: lỗi, quay vòng, đứng im, hết token, câu hỏi chưa trả lời; mỗi sự cố có các cách xử lý cho sếp chọn hoặc ô ghi chỉ đạo), 📣 Báo cáo công việc ngay (lập từ dữ liệu, không tốn quota; có nút tóm tắt bằng AI), 📊 Token (theo model, đơn vị K/M/B; giá USD ghi rõ là "giá trị quy đổi", không phải tiền bị trừ), 📖 Nội quy, 📦 Đóng gói chia sẻ.
- **Thanh CPU / RAM / GPU / VRAM** (ctypes + `nvidia-smi`) và **dải hạn mức** mỗi nhà cung cấp một ô, chừa ô trống cho model mới.
- **Mỗi phòng có ô ra lệnh:** gõ tự do, `@Tên` để chỉ định người; văn phòng tự đoán loại việc (tài liệu, thí nghiệm, review, viết, code, deploy, bảo mật, kỹ năng).
- Mọi hộp thoại **vừa màn hình, cuộn được**, nút Lưu/Đóng dính đáy, kể cả khi giao diện đang phóng to.
- Cập nhật mỗi 1,5 giây; tự gỡ trạng thái "đang làm" giả khi không còn tiến trình nào chạy thật.
- Giao diện xoay vòng: hacker (font mono, neon, mưa ký tự), dễ thương tối, dễ thương sáng.

## 8. An toàn

- Không bao giờ để AI tự nhập mật khẩu hay mã đăng nhập thay người dùng; chỉ mở cửa sổ để người dùng tự làm.
- Khoá SSH, API key: chỉ tham chiếu đường dẫn hoặc biến môi trường, **không chép nội dung** vào lời dặn, kỹ năng hay gói chia sẻ.
- Quyền chạy lệnh (ssh, deploy…) đặt **theo phòng**, chỉ có hiệu lực khi việc ở chế độ ghi **và đã được sếp duyệt**.
- Gói chia sẻ (📦) loại bỏ `state/`, `inbox/`, `outputs/`, khoá và các kỹ năng đánh dấu `private: true`.

## 9. Thứ tự làm

1. Server + `state/` + hộp thư + một nhân viên Claude chạy được một việc chỉ đọc (kiểm thật).
2. Giao diện bàn làm việc, bảng việc, nhật ký.
3. Nhà cung cấp Antigravity / API, hồ sơ nhân viên, đăng nhập, model.
4. Thư ký, Phó sếp, quyền ghi / chạy lệnh.
5. Quy trình cấp bậc + `[CẦN SẾP]` (kiểm bằng **mô phỏng không gọi model** trước).
6. Luồng sự kiện: thao tác, bong bóng suy nghĩ, token thật, hạn mức thật.
7. Bản đồ 3D, mũi tên luồng, các nút Chờ sếp / Sự cố / Báo cáo.
8. Đóng gói chia sẻ, shortcut, chạy không cửa sổ.

Sau mỗi bước: kiểm tra thật trên trình duyệt (không có lỗi console), dọn dữ liệu thử, rồi báo tôi bằng tiếng Việt.
