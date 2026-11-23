# BrightSpeakAI – Gemini Cloud ASR

## Chạy trên Windows

1. Cài Python 3.11 hoặc 3.12 và kết nối Internet.
2. Nhập `GEMINI_API_KEY=...` vào `GEMINI_KEY.txt` (chỉ trên máy cá nhân, không upload lên GitHub).
3. Mở `START-BRIGHTSPEAK.bat` để chạy. Không cài Whisper, PyAV hoặc tải mô hình ASR local.
4. Truy cập website do chương trình mở. Đăng ký qua CAPTCHA (không cần OTP email). Đối với HS cần có đồng thuận người giám hộ.

## Face-to-face

- Chọn hoạt động và câu luyện theo lớp. Bibi được yêu cầu **nói thành tiếng toàn bộ câu hỏi** bằng Gemini Live; câu hỏi hiển thị trên màn hình.
- Câu trả lời mẫu chỉ là gợi ý, không phải đáp án bắt buộc. Nhấn `💡 Gợi ý trả lời` khi HS bí.
- Khi Bibi **đọc xong** mà HS chưa bắt đầu nói trong 5 giây, ứng dụng sẽ hiện gợi ý tự động và yêu cầu Bibi đọc mẫu. Trình duyệt có cơ chế dự phòng đọc tiếng Anh nếu API không phát âm thanh.
- Nếu phát hiện HS bắt đầu trả lời trước 5 giây, bộ đếm sẽ dừng. Khi đổi câu / kết thúc phiên, bộ đếm được hủy.
- Camera tùy chọn; audio và video chỉ gửi theo phiên nếu người dùng cho phép.

## Cần biết

- Gemini ASR dùng Internet và hạn mức API. Lỗi 429/503 có thể xảy ra dù API key hợp lệ; chương trình báo lỗi thật, không tạo transcript/điểm giả.
- Điểm luyện phát âm hiện sử dụng các đặc trưng âm học + đối chiếu transcript, không phải bộ chấm lỗi âm vị đã kiểm định.
- Không dùng tài khoản hoặc dữ liệu trẻ em thật trên bản demo công khai.
- Xem `HUONG_DAN_DEPLOY_CLOUD.md` để đưa mã nguồn lên Render. Mã mới phải nằm tại **gốc repository** cùng `app/main.py` và `requirements.txt`.


## V20 – bản tối ưu tốc độ Luyện phát âm và Look & Speak

Bản vá cùng phiên bản V20 này tham khảo lại cách gọi Gemini đơn giản của V12.
- Luyện phát âm dùng `GEMINI_FAST_MODEL=gemini-3.5-flash-lite` cho ASR; không cài Whisper.
- Look & Speak (ghi âm) gửi ảnh + âm thanh trong **một** lượt Gemini, không gọi hai lần nối tiếp.
- WAV được chuẩn hóa về 16 kHz, ảnh lớn được giảm kích thước trước khi tải lên.
- Không tự bật nhận xét âm thanh bổ sung (`AUDIO_FEEDBACK_ENABLED=false`).
- Thời gian chờ các tác vụ ngắn mặc định 15 giây/lượt, tối đa thử thêm một model dự phòng.
- Nếu API bị giới hạn/quá tải, hệ thống trả lỗi cụ thể, **không bịa transcript hoặc điểm số**.

Đọc `HUONG_DAN_FIX_NHAN_DANG_V20.md` để xem chi tiết. Mức nhanh/chậm thực tế phụ thuộc mạng, Gemini API, độ dài âm thanh và dữ liệu của người học.
