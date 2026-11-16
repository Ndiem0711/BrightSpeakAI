# BrightSpeakAI V13

Ứng dụng hỗ trợ HS tiểu học luyện nói tiếng Anh; giữ các luồng HS/GV/Admin của V12.

Giải nén, điền `GEMINI_KEY.txt` rồi chạy `START-BRIGHTSPEAK.bat`. Cấu hình model tại `AI_MODELS.txt` (Gemini Pro cho hội thoại và ảnh; Live có model riêng). Đọc `HUONG_DAN_V13.txt`.

## Thay đổi

So khớp từ đúng thứ tự và đánh dấu từ thiếu/khác/thêm; kiểm tra bản ghi quá nhỏ hoặc im lặng; nhận xét AI nghe bản ghi; gợi ý bài luyện theo lịch sử và khối lớp. Transcript kiểm thử thủ công không được lưu vào tiến bộ và bị chặn trên cloud. Thêm chẩn đoán AI trong Admin, thông báo lỗi model/key/hạn mức và metadata đánh giá.

Kèm mô hình RandomForest nhận diện từ khóa đã huấn luyện cùng metrics và manifest chia dữ liệu. Đây là thực nghiệm độc lập, không phải mô hình chấm phát âm HS. CNN chỉ có mã huấn luyện tùy chọn.

## Kiểm chứng

`python -m pytest -q --junitxml=docs/qa-v13-junit.xml`

Các cuộc gọi AI trong test được mô phỏng. Chưa xác nhận Gemini Pro/Live bằng key thật, mic/camera vật lý trên Windows hay URL cloud V13. Không suy ra hiệu quả sư phạm từ việc test phần mềm thành công. Xem `docs/QA_V13.md` và `docs/THESIS_MAPPING_V13.md`.

Cloud: xem `docs/CLOUD_V13.md`. Không có tài khoản HS/GV/Admin demo mặc định trên cloud.
