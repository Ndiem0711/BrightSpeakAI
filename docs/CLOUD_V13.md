# Triển khai cloud V13

Trạng thái tại thời điểm bàn giao: **chưa có URL V13 đã triển khai và xác minh**. Tài khoản Render và Railway truy cập được, nhưng phiên này không có quyền ghi repository GitHub để đưa mã nguồn V13 lên nguồn build. Dịch vụ cũ không được thay mã hoặc công bố thành V13.

`render.yaml` tạo web service Python và PostgreSQL riêng tên V13. Mã nguồn cần nằm ở gốc một repository GitHub/GitLab/Bitbucket đã kết nối Render. Không tải `GEMINI_KEY.txt`, `.env`, `runtime/` hoặc bản ghi HS lên repository. Có thể bỏ model ML khỏi cloud vì đây là mô-đun thực nghiệm độc lập.

Các giá trị phải cấu hình trên máy chủ: `GEMINI_API_KEY`, `RESEND_API_KEY`, `MAIL_FROM`, `PUBLIC_BASE_URL`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` (ít nhất 12 ký tự). `SECRET_KEY` được tạo tự động; `DATABASE_URL` lấy từ PostgreSQL; `DEMO_OTP=false`; `APP_ENV=cloud`.

Sau deploy: kiểm tra `/api/v1/system/health` báo `13.0.0` và cloud; đăng nhập Admin; chạy Kiểm tra AI; thử mời tài khoản; thử HS/GV phân quyền; kiểm tra lưu tiến bộ sau khởi động lại; thử mic/Live qua HTTPS. Probe model hội thoại không chứng minh Live hoạt động.

Gói miễn phí chỉ dùng demo và có giới hạn vòng đời tài nguyên; kiểm tra điều kiện trong tài khoản trước khi dùng. Gemini Pro/Live cần hạn mức API riêng; không cam kết miễn phí.

Sites trong ChatGPT không phù hợp để lưu trữ ứng dụng trực tiếp hướng tới trẻ dưới 13 tuổi theo tài liệu Sites đã kiểm tra ngày 16/11/2026: https://learn.chatgpt.com/docs/sites. Không chuyển nhãn ứng dụng thành “dành cho người lớn” để né giới hạn này.
