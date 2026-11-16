# BrightSpeakAI V12 — Data inventory and ML evidence

| Nhóm dữ liệu | Đường dẫn | Trạng thái | Vai trò |
|---|---|---|---|
| 105 cặp Q&A tự biên soạn lớp 1–5 | `data/global_success_original_speaking.json` + `.csv` | Có trong ZIP | Gợi ý Face-to-face, lọc theo khối lớp |
| 125 câu luyện phát âm tự biên soạn | `data/lessons.json` | Có trong ZIP | Luyện phát âm |
| Từ/câu do GV biên soạn | SQLite/PostgreSQL, `lessons` + `teacher_lesson_assignments` | Phát sinh khi sử dụng | Bài giao cá nhân |
| Google Speech Commands | `ml/data/mini_speech_commands/` | Chưa có trong ZIP; tải khi train | ML nhận diện từ khóa, không phải chấm phát âm |
| Audio thật và nhãn lỗi phát âm của HS | Chưa thu thập | Chưa có | Đòi hỏi đồng thuận hợp lệ và GV gán nhãn để đánh giá mô hình |
| Trọng số ML/DL đã huấn luyện | `ml/models/` sau khi train | Chưa có trong ZIP | Chỉ hình thành sau huấn luyện thực tế |

Dữ liệu hỏi–đáp là nội dung mới do dự án biên soạn, gắn nhãn tên Unit tham chiếu các chủ đề Global Success, **không phải dataset hoặc bản sao chính thức của Nhà xuất bản Giáo dục Việt Nam**. Giáo viên cần rà soát từng câu theo chương trình và bộ SGK đã được nhà trường lựa chọn. Không được sử dụng dữ liệu giọng trẻ em thật khi chưa có quy trình đồng ý của người giám hộ và bảo vệ thông tin.

Bản quyền và nguồn tham chiếu: `data/CURRICULUM_AND_LICENSE.md` và metadata `reference_urls` trong JSON. Data tạo bởi GV có quyền thuộc GV/cơ sở giáo dục theo thỏa thuận sử dụng, ứng dụng chỉ dùng cho mục đích giao bài.
