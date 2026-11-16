# Kiểm thử BrightSpeakAI V13 — 16/11/2026

Kết quả chạy cuối: **58 passed**, 1 cảnh báo deprecation từ Starlette/AnyIO; thời gian 5,37 giây. Báo cáo gốc: `qa-v13-junit.xml`. Lệnh: `python -m pytest -q --junitxml=docs/qa-v13-junit.xml`, Python 3.12, môi trường Linux. Bản nền V12 trước sửa: 48 passed.

## Phạm vi đã chạy

Các bài kiểm tra kế thừa bao gồm xác thực/refresh token, phân quyền HS/GV/Admin, OTP và lời mời, phân công HS cho GV, tạo/sửa/ẩn bài GV, lọc bài theo lớp, cấu hình và cơ chế Gemini Live mô phỏng, các kiểm tra mã nguồn và trình khởi động Windows.

10 kiểm thử hành vi V13 bổ sung bao gồm thứ tự từ và từ thiếu; chặn im lặng; không lưu transcript kiểm thử; lưu metadata sau pipeline ASR mô phỏng; quyền truy cập bài gợi ý; bỏ dữ liệu demo khỏi gợi ý; phân quyền chẩn đoán AI; thông báo lỗi model/hạn mức; phân tích JSON phản hồi nghe audio; chặn transcript thủ công trên cloud.

Kiểm tra JavaScript bằng `node --check` cho app.js, features.js và v13.js đã qua. Đây là kiểm tra cú pháp, không thay thế kiểm tra giao diện trình duyệt.

## Thực nghiệm ML đã chạy

RandomForest nhận diện 8 từ khóa: 5.178 mẫu huấn luyện, 1.222 mẫu kiểm tra, chia nhóm theo người nói; Accuracy 61,6%, Macro-F1 0,610. Có artifact, classification report và split manifest trong `ml/models`. Đã nạp artifact và gọi suy luận một WAV công khai. Kết quả còn hạn chế; không được ghi là độ chính xác phát âm hoặc độ chính xác trên HS Việt Nam.

Lần thử trước với tối đa 200 mẫu/lớp chỉ dùng kiểm tra pipeline. Kết quả bàn giao sử dụng cấu hình 800 mẫu/lớp; chưa có tập đánh giá bên ngoài. CNN chưa chạy, không có kết quả CNN.

## Chưa kiểm chứng

Chưa gọi Gemini Pro/Live bằng key thật; chưa có ghi âm hoặc camera vật lý của HS; chưa chấm đối chiếu với GV; chưa đánh giá WER/CER, sai số điểm với người chấm hoặc hiệu quả học tập trước–sau; chưa đo hiệu năng tải đồng thời.

Đã thử khởi chạy kiểm tra trình duyệt headless nhưng môi trường chặn socket của Chromium, nên chưa có kết quả kiểm tra thao tác giao diện bằng trình duyệt trong phiên này. Không coi các kiểm tra mã nguồn/HTTP là kiểm thử giao diện đã hoàn tất. Uvicorn đã khởi động local và các luồng HTTP được kiểm tra bằng TestClient.

Chưa kiểm thử chạy bằng double-click trên Windows; các bài kiểm tra script Windows chủ yếu xác minh logic và nội dung mã.

Cloud V13 chưa triển khai; không có URL production đã xác minh. Đã truy cập được tài khoản dịch vụ nhưng thiếu quyền đưa mã nguồn lên Git remote. Bản cloud phải được kiểm tra health=13.0.0, đăng nhập, lưu kết quả qua restart, email và phiên WSS trước khi ghi “triển khai thành công”.

## Theo dõi lỗi

Ghi tại `BUG_LOG_V13.csv`: ID, mô-đun, mức độ, trạng thái, bước tái hiện, mong đợi, thực tế, cách sửa và minh chứng. Với lỗi mới, bổ sung môi trường/trình duyệt/thiết bị, thời điểm, log đã bỏ key và dữ liệu cá nhân; sau sửa ghi kết quả kiểm tra lại. Không đưa lỗi đang chờ kiểm chứng sang trạng thái Fixed chỉ vì đã thêm mã.
