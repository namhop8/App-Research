# Bài học vận hành văn phòng

Những lỗi đã gặp thật và cách app xử lý. Sửa app thì đọc file này trước, đừng làm lại lỗi cũ.

## Quyền và vòng lặp
1. **Lệnh cần tạo/sửa file mà chạy chỉ đọc sẽ lặp.** Nhân viên hỏi quyền → sếp từ chối → app gửi lại y cũ → hỏi lại.
   App: lệnh tạo đề (phase `ctf`) luôn chạy 📄 Nhận file (ghi được); "📺 Hiển thị" chỉ dùng cho việc đọc/báo cáo.
2. **Sếp "✖ Không đồng ý" một câu [CẦN SẾP] mà không ghi chỉ đạo = dừng việc** (stage `cancelled`), không gửi lại.
   Có ghi chỉ đạo thì mới gửi lại kèm chỉ đạo.
3. **Trả lời "đồng ý cấp quyền" bằng chữ không đổi được chế độ chạy.** Phải bấm 🔓 Cấp quyền ghi / Ghi + chạy lệnh
   (đổi việc sang chế độ ghi, dừng lượt cũ, giao lại ngay, không phải xin lại).
4. **Thiếu quyền thì hỏi đúng 1 lần** bằng [CẦN SẾP], nêu rõ quyền cần (ghi thư mục nào, chạy lệnh gì). Không hỏi lại
   cùng một thứ (ghi trong Sổ nội quy).

## Tạo đề CTF
5. **Vòng "làm lại cho tới khi ĐẠT" phải có giới hạn cứng.** tools/tester.py đếm `tries` (trượt liên tiếp) trong
   `<gói>/_thu-de.json`; người tạo đề tự thử quá 3 lần thì bị chặn và phải [CẦN SẾP] kèm 2-3 hướng thiết kế khác.
   Sếp bấm 🧪 Thử ở Phòng Thử đề thì không giới hạn. Đề ĐẠT thì đếm lại từ 0.
6. **Đề tạm ở `E:\CTF\challenges\nhap\<gói>\`.** Mò (AI thử mù) chỉ nhận mô tả + file phát trong `E:\CTF-ThuDe\`,
   không có nội quy/skill/vai trò; đề có máy dựng container tạm trên VPS (127.0.0.1) + đường hầm SSH.
7. **Danh sách đề phải lấy từ bản xuất portal** (`challenges\_vps\<ngày>\portal-export`), máy không có đủ bản gốc.

## Giao diện
8. **Hồ sơ nhân viên ở phòng hệ thống** (Mò ở Phòng Thử đề): ô "Phòng" phải luôn có phòng hiện tại, nếu không bấm
   Lưu sẽ chuyển người đó sang phòng khác.
9. **Thư hỏi sếp đã trả lời/bỏ qua phải đổi thành `.done.md`**, nếu không mũi tên trên bản đồ còn mãi.
10. **Ô gõ trong phòng:** khi đang gõ thì không vẽ lại phòng (mất chữ, mất con trỏ).

## Khởi động lại
11. Không khởi động lại khi có người đang làm (trừ khi lượt đó chỉ đọc). Sửa tools/tester.py không cần khởi động lại
    (văn phòng tự nạp lại); sửa office.py / workers.py / workflow.py thì phải khởi động lại lúc mọi người rảnh.

## Dừng tiến trình
12. **Hết giờ / dừng phải diệt CẢ CÂY tiến trình** (taskkill /T /F). Chỉ diệt claude.exe thì bash/python con vẫn giữ
    luồng ra, app đứng chờ mãi (Mò chạy quá 2 phút dù giới hạn 120 s). providers._stream và workers.cancel_task dùng cây.
13. **Mò do người tạo đề gọi chạy thành nhánh riêng:** dừng người tạo đề xong phải dọn Mò mồ côi
    (office._kill_testers: tester.py / CTF-ThuDe / ctftest-). Mọi nhân viên (cả Thư ký, Phó sếp, Mò) có ■ Dừng
    khi đang chạy; mỗi phòng có ■ Dừng cả phòng.

## Phân việc và chống quay vòng
14. **Mặc định "🤖 Tự chọn theo độ khó"** (workflow.classify, không tốn lượt AI): việc cơ bản (hỏi, xem, tìm, ý tưởng)
    → 1 người làm, xong trình sếp; việc vừa (code, deploy, tạo đề, rà bảo mật) → 1 người làm + trưởng phòng duyệt;
    việc sâu (toàn bộ/chi tiết/thí nghiệm/viết paper, hoặc lệnh dài) → trưởng phòng chia người + duyệt 2 cấp.
    Mặc định cũ "Đầy đủ" cho mọi việc làm việc nhỏ cũng tốn 3-4 lượt AI. Trưởng phòng chia ít người nhất, tối đa 3.
15. **Sếp "đồng ý" câu [CẦN SẾP] xin quyền = cấp quyền thật** (đổi việc sang chế độ ghi). Trước đây #43, #44 bị hỏi
    lại 9 lần vì chữ "ok cấp quyền" không đổi chế độ chạy.
16. **Ngân sách lượt:** mỗi việc tối đa 8 lượt AI (làm + duyệt + hỏi); quá thì dừng hỏi sếp một lần, sếp trả lời thì
    thêm 4 lượt. Hỏi sếp lần thứ 4 cho cùng một việc thì việc tự dừng.

## Phản biện mù và công cụ riêng
17. **Việc chạy bằng công cụ riêng (phản biện mù, thử đề) phải đánh dấu `external`**: không có nút 🔓 giao lại, grant_task
    từ chối. Trước đây sếp bấm 🔓 trên kết quả lỗi → việc bị giao lại theo luồng thường (Gemini đọc cả D:\Paper3,
    Claude duyệt, trả lại) → mất "mù" và trông như lặp.
18. **Antigravity ở chế độ chỉ đọc không mở được file PDF/đọc thư mục bằng lệnh** (bị chặn → "no output produced").
    Phản biện mù đưa thẳng chữ của PDF vào lời nhắn, chia đoạn ≤15k ký tự, thư mục làm việc trống.
19. **Kết quả phải có một chỗ để đọc:** nút 📚 Kết quả (mọi việc có output, 🆕 = chưa đọc, lọc phòng/người).
20. **Khung kết quả phải có lối ra:** việc chưa đóng có ✅ Xong (đã xem) và ■ Dừng hẳn, không chỉ có 🔓 làm tiếp
    (chỉ có nút làm tiếp thì sếp dễ bấm nhầm và việc chạy lại).
21. **Công cụ mới gọi model phải chạy thử với 1 lần thật nhỏ trước** khi giao việc lớn. Phản biện mù tốn 4 lần (3 lần
    lỗi quyền của Antigravity: lệnh, ghi file, lệnh) mới ra cách đúng: đưa thẳng chữ vào lời nhắn.

## Chạy lặp phải có lý do
22. **Mỗi lượt chạy AI của một việc ghi lý do** (`task.run_log`, office.note_run; thư có dòng `reason:`): lần đầu,
    trưởng phòng/Phó sếp duyệt, bị trả lại (kèm vấn đề), sếp trả lời [CẦN SẾP], sếp bấm 🔓, sếp xử lý ở 🛠️ Sự cố,
    ngủ dậy sau khi hết token, thử lại sau lỗi mạng. Hiện ở 👁 Đang làm gì, 📚 Kết quả ("Vì sao chạy N lượt"),
    thẻ việc (🔁 N lượt, rê chuột xem lý do) và trạng thái nhân viên ("· lượt 3 vì: …").
23. **Lỗi không được thử lại mù.** Trước đây mọi lỗi đều tự chạy lại sau 2 phút, y hệt, và hỏng y hệt.
    Giờ workers.classify_error chia: chưa đăng nhập / bị chặn quyền / lỗi mạng / quá giờ / chưa rõ. Chỉ lỗi mạng
    được tự thử lại ĐÚNG 1 lần; còn lại đóng thư, dừng việc và hỏi sếp 1 lần kèm phương án (⏳ Chờ sếp).
    Lỗi ở bước duyệt: sếp đồng ý thì chạy lại đúng bước duyệt, không bắt người làm làm lại. Hết giờ giờ báo rõ
    "Hết giờ: lượt chạy quá N giây" (providers._stream) thay vì "thoát với mã 1".

## Người tạo đề không tự giải đề
24. **Người tạo đề chỉ TẠO ĐỀ + VIẾT solve.py** (sếp chốt 2026-10-24, sau việc #53: Ổi tự chạy solve.py mô phỏng
    hàng chục lần, quá giờ 30 phút). Cờ `maker: true` trên hồ sơ → workers không cho lệnh terminal (chỉ Read/Write/Edit),
    kể cả khi sếp bấm 🔓. Nộp xong, workflow tự giao Mò thử MÙ (office.tester_run_wait, stage `blind_test`):
    TRƯỢT → trả lại người tạo đề kèm cách Mò giải; thiếu challenges.json → trả lại; lỗi/⛔ → hỏi sếp; ĐẠT → trưởng
    phòng duyệt → sếp ký → Mít đăng NHÁP. Vai trò, nút việc của 6 người tạo đề và 2 skill CTF đã ghi rõ phân vai.
25. **Mò full quyền đọc/ghi/lệnh/web, chỉ CẤM đọc lời giải** (sếp chốt 2026-10-24). tester.py: --add-dir C:\ D:\ E:\, Bash không giới hạn, và --disallowedTools Read/Edit/Write/Grep/Glob(//e/CTF/**, //e/ResearchLab/**, lịch sử chat) chặn cứng (đã chạy thử bằng haiku: E:\CTF bị chặn, chỗ khác đọc được). Lệnh Bash không chặn được theo đường dẫn nên soát TOÀN BỘ tham số công cụ (providers.TOOL_LOG): đụng E:/CTF/, ResearchLab, secret.json, _thu-de, .claude/projects (kể cả cố đọc mà bị chặn) → kết quả "loi" KHÔNG TÍNH. Regex chữ ổ đĩa phải là `(?<![a-z])` (http:// có "p:/"); E:\CTF-ThuDe (thư mục thử) không bị tính; Mò tự đặt tên script solve.py là bình thường.
26. **Nhân viên ngồi phòng khác vẫn theo quy định phòng gốc:** `work_dept` (vd. Mít ngồi Phòng Thử đề cạnh Mò, làm theo
    quy định/lệnh/thư mục của Phòng CLB). workers dùng work_dept; nút việc gửi về work_dept; tester_deploy tìm người deploy
    theo dept hoặc work_dept = clb.
27. **Đề "đã đăng" mà portal không hiện:** portal chỉ hiện 9 mảng cố định (app/__init__.py CATEGORIES: Web, Pwn, Crypto,
    Reverse, Forensics, OSINT, Misc, Hardware, Prompt Security). reg_challenges.py từng đổi `ai` → "AI Security" (không có
    trong danh sách) nên đề #81 có trong DB, published, máy chạy, nhưng không ai thấy. Đã đổi `ai` → "Prompt Security".
    Báo cáo "đã đăng" phải kiểm cả mảng nằm trong CATEGORIES, không chỉ status trong DB.
28. **Phòng chốt quy trình** (`dept.flow`, vd. Phòng Game = "fast"): mọi lệnh vào phòng đi thẳng làm → sếp duyệt, không
    qua trưởng phòng / Phó sếp, không vòng trả lại. Việc lớn chia BƯỚC trong file đề (BRIEF_ART.md), mỗi bước một việc,
    sếp duyệt xong mới giao bước sau (thay cho vòng duyệt tự động).
29. **Chuỗi tự động khi sếp vắng** (`dept.chain` = danh sách bước {owner,title,text}, `chain_pos`, `chain_check` =
    lệnh máy kiểm tra, `timeout` mỗi lượt): bước xong → máy kiểm tra đạt thì tự duyệt (`auto_signed`) và giao bước sau;
    chưa đạt thì trả lại tối đa 2 lần rồi để chờ sếp, chuỗi đi tiếp; hết giờ thì làm tiếp phần dở (tối đa 3 lần);
    [CẦN SẾP] về nội dung → bước đó chờ, chuỗi đi tiếp. LỖI KHI CHẠY thì DỪNG chuỗi: lần đầu chạy, văn phòng mở qua
    Explorer không đọc được AppData (không thấy `claude`), chuỗi cứ giao tiếp → 4 bước lỗi dây chuyền trong vài giây.
30. **Mở văn phòng để sống lâu hơn phiên chat:** mở qua Explorer từ phiên Claude thì tiến trình không đọc được
    C:\Users\...\AppData (find_bin = None); `cmd start` bị chặn quyền. Văn phòng bật từ phiên chat sẽ tắt theo phiên,
    nên chạy lâu thì sếp tự mở bằng shortcut Desktop (bấm tay, không qua phiên Claude).
31. Không mở quyền chạy lệnh cho Antigravity bằng `permissions.allow` trong ~/.gemini/antigravity-cli/settings.json:
    bộ phân loại an toàn của Claude Code chặn (làm yếu bảo mật). Nhân viên cần chạy python thì dùng claude-cli.
32. **App Claude là gói MSIX: npm cài từ trong phiên chat bị "ảo hoá".** `claude` cài bằng npm từ phiên Claude (23/10)
    nằm thật ở %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\npm\, không phải %APPDATA%\npm. Phiên chat thấy file,
    văn phòng mở bằng shortcut thì không → "Chưa cài Claude Code". providers.find_bin dò thêm chỗ đó. Văn phòng nên mở
    bằng shortcut (Explorer) để chạy độc lập với phiên chat; giờ cách này dùng được.
33. **Chuỗi có nhóm song song:** một bước của dept.chain có thể là {"group": [việc, việc…]} → giao cùng lúc cho nhiều
    người, `chain_wait` đếm việc còn lại, đủ cả nhóm xong (đạt / để chờ sếp) mới sang bước sau (workflow.chain_done).
    Chỉ cho song song những phần không phụ thuộc nhau, SAU bước làm mẫu phong cách. Đổi code chuỗi khi đang chạy: cất
    chuỗi (chain=None) để code cũ dừng ở chờ ký, khởi động lại lúc rảnh, nạp lại chuỗi, rồi chain_next.
34. **Lệnh có biến môi trường đứng trước bị chặn:** RULES mục 4 (giới hạn 2 thread) khiến nhân viên gõ
    `OMP_NUM_THREADS=2 python …` / `export …` → không khớp Bash(python:*) → bị chặn, nhân viên dừng hỏi sếp (Bánh, Kem, Su).
    Giờ providers.env_with_key đặt sẵn các biến thread cho mọi lệnh và RULES ghi "chỉ gõ `python …`".
35. **Chuỗi song song phải đếm mỗi việc MỘT lần, và câu hỏi chờ sếp không phải là xong.** Bánh hỏi 2 lần bị trừ 2 →
    V2-6, V2-7 bị giao khi nhóm chưa xong. chain_done(dept, task_id) giữ chain_done_ids; need_boss không đẩy chuỗi nữa.
36. **Gemini (Antigravity) vẽ được khi có luật trong ~/.gemini/antigravity-cli/settings.json** (sếp tự sửa: command /
    read_file / write_file). Chạy thử từ phiên chat Claude vẫn bị chặn ("unsandboxed"), chạy qua văn phòng mở bằng shortcut
    thì được (#87 đạt 2026-10-28). Thử nhân viên Antigravity luôn qua văn phòng, không qua phiên chat.
37. **Sonnet tưởng mình "chỉ đọc" dù có quyền:** AUTO_NOTE có câu "Ở chế độ chỉ đọc: KHÔNG chạy lệnh", dòng quyền chỉ ghi
    "được sửa file" → Kem / Su / Bánh không dám chạy python, dừng hỏi sếp. Dòng quyền giờ ghi rõ "ĐƯỢC SỬA FILE VÀ ĐƯỢC
    CHẠY LỆNH … KHÔNG phải chế độ chỉ đọc" khi phòng / người có quyền lệnh.
38. **Chạy lại script cũ có thể ghi đè bản mới:** FIN-2 phát hiện cả assets/ui/ là bản V2 (giống từng byte bản lưu trữ)
    vì có người chạy lại make_ui.py sau khi đã làm UI Avatar. Khi đổi phong cách, script cũ phải đổi tên / trỏ sang bản mới,
    và bước rà cuối luôn so asset với bản lưu trữ (_v2_old) để bắt ghi đè.
39. **Code song song cùng một repo thì phải chia thư mục.** G-4: Ốc, Cua, Sò cùng sửa shared/src (và thư mục nháp
    .g4b-draft) → ghi đè nhau, build đỏ, cả 3 dừng hỏi sếp lúc 4–5 giờ sáng. Luật mới của Phòng Dev Game: mỗi người chỉ
    sửa thư mục của mình (server/, client/, content/), shared/ chỉ trưởng nhóm sửa; gộp ở bước tổng hợp.
40. **Lịch kiểm (cron) chỉ sống trong phiên chat.** Phiên khởi động lại qua đêm → cron mất, câu hỏi nằm chờ 2 giờ. Sau
    mỗi lần phiên mở lại phải đặt lại lịch kiểm.
41. **Docker Desktop trên Windows 10 cần WSL2 bản mới:** `wsl --update` lỗi 0x80072f8f (TLS bị chặn) → tải gói WSL chính thức
    bằng `winget download --id Microsoft.WSL` rồi sếp cài bằng `Add-AppxPackage` (cần Admin). Cài xong phải mở lại Docker
    Desktop. Server game chỉ bật sandbox khi lúc khởi động thấy `docker` trong PATH và đủ image gcc:13 / python:3-slim /
    bash:5 / alpine/git.
42. **Ghi chú Phòng Kỹ năng dính vào mọi việc của phòng `auto_write`.** `_deliver_note` gắn SKILL_NOTE ("tự tìm skill trên
    web, tải về…") cho mọi phòng có auto_write, nên Phòng Game / Dev Game làm việc nào cũng đi tìm skill trước → chậm, sinh
    mục "📬 Kỹ năng cho…". Đã sửa: chỉ phòng `skills` mới có ghi chú này (cần khởi động lại văn phòng để có hiệu lực).
43. **Hết token → nhân viên ngủ tới giờ nhà cung cấp hẹn, kể cả khi tài khoản đã dùng lại được.** Đánh thức bằng
    `office.set_status(id, "idle", …)`. Lúc giao việc mà người được gọi đang ngủ thì `acting()` cho người khác làm thay,
    nên phải kiểm `owner` sau khi giao.

## 2026-10-30: đoán loại việc nhầm vì từ khoá nằm trong đường dẫn
- Việc vẽ tóc giao cho Gem bị đoán là "review" vì chữ `previews/hair_fit/` chứa "review" → worker chèn lời dặn phản biện paper (Reviewer 2), Gem hỏi lại.
- Sửa: PHASE_GUESS dùng `\breview\b`. Khi thêm từ khoá đoán loại việc, luôn dùng ranh giới từ để tên thư mục / file không khớp nhầm.
- Cùng lúc phát hiện PHASE_GUESS "lit" có `\bq1\b` bị lưu thành ký tự lùi (0x08) từ trước, nên "q1" không bao giờ khớp. Đã sửa; sửa regex trong file .py thì dùng Edit, đừng đi qua heredoc / sed (\b dễ biến thành 0x08). Kiểm: `grep -rlP "\x08" tools/`.
- Có hiệu lực sau lần khởi động lại văn phòng kế tiếp.
- 30/10 lần 2: chữ "soát" đứng một mình (vd. "Bộ soát chữ" trong thư giao việc game) cũng làm việc vẽ / code bị đoán là review. Giờ chỉ khớp "soát bài / bản thảo / paper / lỗi chính tả".
- 30/10 lần 3: Sứa (phòng game) nhận việc code bảng phó bản nhưng thư có chữ "theo tài liệu" → đoán "lit" → Sứa viết tổng quan tài liệu Q1. Sửa gốc trong _room_command: phòng khác research thì loại lit / review / writing / idea / design / experiment / results đổi thành "code". Có hiệu lực sau khi khởi động lại văn phòng.
