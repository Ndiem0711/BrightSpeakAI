# TRIỂN KHAI BrightSpeakAI TRÊN RENDER — BẢN MÃ NGUỒN MỚI

**Trạng thái bàn giao:** Gói mã nguồn đã qua kiểm thử tự động tại môi trường xây dựng. **Chưa push GitHub và chưa xác nhận Render Live**. Không nhập dữ liệu HS thật vào demo Cloud.

## A. Đẩy mã nguồn vào ĐÚNG thư mục gốc GitHub

1. Giải nén `BrightSpeakAI_V20.zip` ra một thư mục mới. Cài Git for Windows và đăng nhập tài khoản GitHub có quyền ghi repository `Ndiem0711/BrightSpeakAI`.
2. Nhấp đúp **`DEPLOY-CLOUD.bat`**, xem danh sách tệp và nhập `YES` khi đồng ý cập nhật. Script sẽ `git clone`, sao chép thư mục `app/` và file `render.yaml` đến **gốc repository**, rồi push nhánh `main`. Script loại trừ key, `.env`, dữ liệu local và log.
3. Kiểm tra trên GitHub có các đường dẫn **`app/main.py`**, **`app/__init__.py`**, **`requirements.txt`**, **`render.yaml`** trực tiếp tại gốc. Không upload nguyên folder ZIP vào một thư mục con; đây là nguyên nhân khiến Render báo `No module named 'app'`.
4. Mã nguồn chỉ được deploy khi đã có commit mới. Cập nhật file ZIP ở máy tính **không tự cập nhật** repository đang kết nối Render.

## B. Blueprint đã tạo: không tự động tạo database trùng

Tài khoản Render hiện có Blueprint `brightspeakai-cloud` và PostgreSQL tên `brightspeakai` (không có chữ V13). `render.yaml` mới giữ tên **database `brightspeakai`**, đề xuất Web Service tên **`brightspeakai-app`**. Việc đổi tên dịch vụ trong Blueprint có thể khiến Render tạo dịch vụ mới và ngừng quản lí dịch vụ cũ. **Xem màn hình kế hoạch thay đổi (plan/diff) trước khi áp dụng**; không chấp nhận tạo thêm PostgreSQL ngoài ý muốn. Không xóa DB cũ khi còn dữ liệu.

Vì Blueprint auto-sync theo `main`, push có thể kích hoạt kế hoạch sync. Theo dõi: https://dashboard.render.com — chọn Blueprint và kiểm tra `Syncs` hoặc Web Service `Events`.

## C. Cấu hình môi trường trên Render (không nhập key vào GitHub)

- `APP_ENV=cloud`
- `REGISTRATION_MODE=captcha` (đăng ký không OTP)
- `ASR_ENGINE=gemini` (Cloud free: không cài Gemini nặng)
- `GEMINI_API_KEY` = key thực tế, **nhập riêng tại Render → Web Service → Environment**; không chia sẻ vào file/ảnh/chat.
- `SECRET_KEY` = chuỗi bí mật ngẫu nhiên tối thiểu 32 ký tự; Render có thể tự tạo.
- `DATABASE_URL` = kết nối từ PostgreSQL được liên kết qua Blueprint. Không thay bằng SQLite.
- `BOOTSTRAP_ADMIN_EMAIL` = email Admin mong muốn.
- `BOOTSTRAP_ADMIN_PASSWORD` = mật khẩu Admin mạnh, do bạn tự nhập tại Render.
- `PUBLIC_BASE_URL` chỉ điền khi biết chính xác URL Render được cấp (không bắt buộc cho CAPTCHA).

Dùng Python **3.12.9**, Render cài dependency từ `requirements.txt` và `requirements-cloud.txt`. Build command có kiểm tra `app/main.py` ở gốc GitHub, và import backend. Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## D. Kiểm chứng sau khi Render chạy

1. Mở đường dẫn Render cấp, sau đó kiểm tra `/api/v1/system/health` trả `status=ok`, `version=20.0.0`, `captcha_required=true`, `asr_provider=gemini` (đây là trạng thái cấu hình, không chứng nhận Google API hoạt động).
2. Đăng ký HS bằng CAPTCHA ảnh (không OTP), kiểm tra đăng nhập. Admin có thể tạo GV/HS trực tiếp, không qua email.
3. Kiểm thử nhiều lượt ghi âm liên tiếp, hội thoại giọng nói, Look & Speak và Gemini Live. Kiểm tra log Render nếu có mã lỗi 429 (quota), 503 (dịch vụ bận), 401/403 (API key/quyền model).
4. Kiểm tra các bản ghi không hợp lệ / im lặng KHÔNG được chấm điểm; kiểm tra kết quả được lưu sau khi đã xác thực và nhận dạng thành công.
5. **Chỉ gọi là Cloud đã triển khai thành công sau khi trạng thái `Live` và kiểm thử từ trình duyệt ngoài.**

**Lưu ý:** Render Free có giới hạn và PostgreSQL Free có thể hết hạn; CAPTCHA nhập hình không xác minh quyền sở hữu email. Việc dùng dữ liệu trẻ em thật cần quy trình đồng thuận và bảo vệ dữ liệu riêng.


## Cấu hình tốc độ dành cho bản V20 cập nhật

Trong **Render → Web Service → Environment**, xác nhận các biến:

```text
GEMINI_FAST_MODEL=gemini-3.5-flash-lite
GEMINI_FAST_FALLBACK_MODEL=gemini-3.8-flash
GEMINI_FAST_TIMEOUT=15
AUDIO_FEEDBACK_ENABLED=false
```

`render.yaml` đã có các giá trị trên. Biến môi trường đang thiết lập thủ công trên Render có thể được ưu tiên và cần kiểm tra khi đồng bộ Blueprint. Tiếp tục nhập `GEMINI_API_KEY` qua Environment (không commit lên GitHub). Không thay đổi `GEMINI_LIVE_MODEL` và cấu hình database hiện có khi chỉ muốn cập nhật tính năng.

Nếu vẫn gặp lỗi AI, vào **Logs** và trang quản lí hạn mức Google AI Studio, xem mã `429`, `503`, `401/403`, hoặc `404`; không đăng công khai khóa API.
