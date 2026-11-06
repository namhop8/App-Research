# ResearchLab

Văn phòng nhiều nhân viên AI, quản lý bằng một app chạy trên máy (http://localhost:8765).

**Mở văn phòng:** bấm đúp `MoVanPhong.bat`. Lần đầu sẽ tự tạo shortcut "Văn phòng ResearchLab" trên Desktop.
App mở thành cửa sổ riêng, không có cửa sổ đen; tắt bằng nút ⏻ trên app.

## Chia sẻ cho người khác

Bấm 📦 trên app (hoặc `python tools/office.py pack`) để tạo `dist/ResearchLab-<ngày>.zip`.
Gói chỉ có code, quy tắc và khung project, **không kèm** API key, nhân viên, nhật ký, thư hay kết quả của bạn.
Người nhận cần Windows + Python 3 (chưa có thì `MoVanPhong.bat` sẽ chỉ cách cài): giải nén ở đâu cũng được rồi bấm `MoVanPhong.bat`.
Muốn nhân viên AI làm việc thật thì cài và đăng nhập ngay trong app (bấm vào nhân viên → ⬇️ Cài đặt → 🔑 Đăng nhập; cần Node.js).

## Trong văn phòng

- **🛎️ Quầy lễ tân**
  - **Tèo** (Thư ký, đổi tên được): khi nhân viên cần quyền sửa file, cần chạy lệnh deploy hoặc cần đăng nhập, Tèo mang lên hỏi sếp. Bấm 🔔 để nhận thông báo.
  - **Phó sếp**: giữ "lệnh thường trực" của sếp (ví dụ *"cứ deploy hết đi"* cho phòng CLB) và duyệt thay khi khớp. Những việc nguy hiểm (`rm -rf`, `prune`, `push --force`, `DROP TABLE`…) và việc đăng nhập thì Phó sếp không bao giờ duyệt thay.
- **Phòng ban** (🔬 Nghiên cứu, 🌐 Web & Deploy, 🛡️ CLB An ninh mạng, thêm được phòng mới): mỗi phòng có thư mục làm việc và quy định riêng.
- **Nhân viên**: bấm vào một người để chọn nhà cung cấp, chọn model, cài đặt, đăng nhập, nhập API key, kiểm tra kết nối, đổi phòng, đổi diện mạo hoặc cho nghỉ việc. Bấm vào bàn trống "＋" để tuyển người mới.

## Nhà cung cấp hỗ trợ

| Loại | Đăng nhập |
|---|---|
| Gemini CLI | nút 🔑 mở terminal → Sign in with Google (hoặc API key) |
| ChatGPT / Codex CLI | nút ⬇️ cài, 🔑 đăng nhập tài khoản ChatGPT (hoặc API key) |
| Claude Code | nút 🔑 → /login (dùng chung tài khoản với Claude Desktop) |
| API kiểu OpenAI | địa chỉ API + model + key: MiMo, DeepSeek, OpenRouter, Ollama… |
| Tự báo cáo | Antigravity và các app khác, tự chấm công bằng `tools/office.py` |

Thêm loại mới: khai báo trong `tools/providers.py` (PRESETS + cli_argv).

## Giao việc

Gửi thư từ app (hoặc `office.py mail`). Nhân viên bật "tự nhận thư" sẽ tự làm và ghi kết quả vào `outputs/<nhân viên>/`.
- **Chỉ đọc** (mặc định): trả về báo cáo, review hoặc patch.
- **Được sửa file**: Thư ký xin sếp duyệt trước (hoặc Phó sếp duyệt theo lệnh), rồi mới làm trong thư mục của phòng.

## File

```
RULES.md                  quy tắc chung (mọi nhân viên đọc)
CLAUDE.md / GEMINI.md / AGENTS.md
state/office.json         nhân viên, phòng ban, việc, yêu cầu duyệt, lệnh của Phó sếp
state/secrets.json        API key (chỉ trên máy này, app không bao giờ hiện lại)
state/activity.jsonl      nhật ký
inbox/                    thư giao việc
outputs/                  kết quả nhân viên làm
tools/office.py           server + CLI · providers.py nhà cung cấp · workers.py nhân viên tự làm
app/index.html            giao diện
projects/_template/       khung cho mỗi paper
```

## Sửa app
Trước khi sửa code văn phòng (tools/, app/), đọc BAI_HOC.md: các lỗi đã gặp thật và cách đã xử lý.

## Dành cho người nhận repo (dùng Codex)

Repo này chỉ có **code + quy tắc + khung**. Không có API key, nhân viên, nhật ký, thư hay kết quả của chủ cũ
(các thư mục `state/`, `inbox/`, `outputs/` bị `.gitignore` và app tự tạo lại khi chạy lần đầu).

### Chạy

- Cần **Windows + Python 3.10+** (chỉ thư viện chuẩn, không `pip install` gì). Node.js chỉ cần khi cài CLI cho nhân viên.
- Bấm đúp `MoVanPhong.bat`, hoặc: `python tools/office.py serve --open` → http://localhost:8765
- Lần đầu: bấm vào một nhân viên → chọn nhà cung cấp (vd **ChatGPT / Codex CLI**) → ⬇️ Cài đặt → 🔑 Đăng nhập (bạn tự đăng nhập trong cửa sổ terminal; app không bao giờ nhập mật khẩu thay bạn).
- CLI không cần mở app: `python tools/office.py status|log|task|mail|pack ...` (xem `-h`).

### Sửa app bằng Codex

Mở Codex ở thư mục gốc repo. Codex đọc `AGENTS.md` (mục "Khi sửa code của app"). Tóm tắt luật:

1. **Đọc `BAI_HOC.md` trước**: các lỗi đã gặp thật (Windows `.cmd` cắt tham số xuống dòng, diệt cả cây tiến trình, vòng làm lại phải có giới hạn cứng…).
2. Backend chỉ **thư viện chuẩn Python**; frontend là **một file** `app/index.html` (HTML/CSS/JS thuần, không build).
3. Không ghi cứng đường dẫn máy, IP, khoá. Mọi đường dẫn tính từ thư mục gốc app; cấu hình riêng đặt trong `state/` hoặc biến môi trường.
4. Ghi file trạng thái phải **nguyên tử** (ghi file tạm rồi `os.replace`) và qua khoá có sẵn trong `office.py`.
5. Server chỉ nghe `127.0.0.1`, giữ kiểm `Host` / `Origin` / `Content-Type` (chống DNS rebinding).
6. Thêm nhà cung cấp AI mới: khai báo trong `tools/providers.py` (`PRESETS` + `cli_argv`), không sửa giao diện.
7. Kiểm nhanh sau khi sửa: `python -m py_compile tools/*.py`, rồi chạy `python tools/office.py serve --open` và thử thao tác vừa sửa. Sửa `office.py` / `workers.py` / `workflow.py` thì khởi động lại app (nút ⏻ rồi mở lại) lúc không có nhân viên đang làm.

| File | Vai trò |
|---|---|
| `tools/office.py` | server HTTP + CLI + trạng thái văn phòng (nhân viên, phòng, việc, duyệt) |
| `tools/workers.py` | nhân viên tự nhận thư, chạy nền, ngủ khi hết quota |
| `tools/providers.py` | gọi Claude Code / Codex / Gemini / Antigravity CLI và API kiểu OpenAI |
| `tools/workflow.py` | quy trình nhiều cấp duyệt theo phòng |
| `tools/tester.py` | phòng Thử đề CTF (AI giải mù); máy chạy đề tạm cấu hình qua `CTF_VPS` hoặc `state/ctf_vps.txt` |
| `tools/troubleshoot.py`, `sysmon.py`, `blind_review.py` | chẩn đoán, theo dõi máy, phản biện mù |
| `app/index.html` | toàn bộ giao diện |
| `skills/` | kỹ năng dùng chung nhân viên đọc khi làm việc |
| `PROMPT_DUNG_APP.md` | đặc tả gốc để dựng lại app từ đầu |
