# BrightSpeakAI V20 – Khắc phục tốc độ nhận dạng và Look & Speak

## Đối chiếu V12 và V20 trước sửa
- V12 gọi Gemini một lần với Flash-Lite mặc định, timeout 35 giây.
- V20 mặc định dùng Flash lớn hơn, có thể thử nhiều lần trên hai model và có thể thực hiện nhận xét âm thanh phụ, làm thời gian chờ kéo dài.
- Look & Speak V20 gửi giọng nói đến Gemini để ASR rồi gửi hình ảnh+transcript ở một cuộc gọi thứ hai.

## Điều chỉnh trong bản V20 này
- **Pronunciation:** dùng `GEMINI_FAST_MODEL=gemini-3.5-flash-lite` cho ASR; tối đa một lượt gọi model chính và một lượt gọi model dự phòng. Timeout mặc định 15 giây/lượt.
- **Look & Speak:** một yêu cầu Gemini gồm WAV+ảnh để nhận dạng và nhận xét sự phù hợp nội dung. Không còn chuỗi hai API calls. Bản văn bản vẫn xử lí ảnh bình thường.
- **Ghi âm:** chuẩn hóa WAV về PCM mono 16 kHz trước khi gửi, giảm kích thước tệp.
- **Hình ảnh:** khi ảnh lớn, trình duyệt nén về tối đa 1024 pixel chiều lớn trước khi gửi (chỉ khi ảnh nén nhỏ hơn).
- **Mặc định:** `AUDIO_FEEDBACK_ENABLED=false`; nếu bật sẽ thêm một cuộc gọi Gemini và tăng độ trễ.
- **Lỗi:** phân biệt hạn mức 429, quá tải 503, phản hồi sai định dạng và không có lời nói; không làm giả transcript hoặc điểm số.
- **Giữ nguyên:** tên và version 20.0.0, Face-to-face, Bibi gợi ý sau 5 giây, CAPTCHA, phân quyền, cấu hình Cloud.

## Tùy chỉnh
Trong `AI_MODELS.txt` (local) hoặc môi trường Render:
- `GEMINI_FAST_MODEL=gemini-3.5-flash-lite`
- `GEMINI_FAST_FALLBACK_MODEL=gemini-3.8-flash`
- `GEMINI_FAST_TIMEOUT=15`
- `AUDIO_FEEDBACK_ENABLED=false`
Đặt biến môi trường trên Cloud riêng; không đưa khóa API lên GitHub.

## Giới hạn
Bản kiểm thử tự động không chứng minh được độ trễ thực tế hoặc chất lượng nhận dạng trên micro, tài khoản Gemini và Cloud của người dùng. Một yêu cầu Gemini có thể gặp 429/503 dù đã giảm tải. Cần kiểm thử bằng âm thanh trẻ em thực tế và đo thời gian `latency_ms`.
