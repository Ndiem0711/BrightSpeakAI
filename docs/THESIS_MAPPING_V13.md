# Đối chiếu V13 với sườn đồ án

| Mục đồ án | Mã nguồn/minh chứng | Phạm vi thực tế |
|---|---|---|
| 3.2, 4.2 Chức năng, frontend/backend | app/main.py, app/static/ | Giữ luồng HS/GV/Admin, giao bài và các chế độ luyện nói |
| 3.4, 4.3 Nhận dạng và đánh giá phát âm | app/asr.py, app/scoring.py, app/audio_feedback.py | ASR qua dịch vụ/cài Whisper tùy chọn; so khớp từ và proxy âm học; AI nghe bản ghi để góp ý. Chưa có căn chỉnh/chấm âm vị đã kiểm định |
| 3.5, 4.5 Cá nhân hóa | app/adaptive.py, /api/v1/learning/recommendations | Quy tắc dựa trên khối lớp, lịch sử, bài yếu và độ dài câu. Không phải mô hình học lộ trình từ dữ liệu HS |
| 4.3 ML/DL | ml/models, ml/train_keyword_spotter.py, ml/train_cnn_keyword_spotter.py | RF đã huấn luyện trên dữ liệu công khai; CNN chưa chạy; không dùng độ chính xác từ khóa thay cho độ chính xác phát âm |
| 4.4 Hội thoại, Gemini Live | app/gemini.py, app/live.py | Có mã kết nối; cần kiểm chứng dịch vụ thật và thiết bị |
| 3.3, 4.5 Cloud | Dockerfile, render.yaml | Có cấu hình V13. Chưa triển khai V13 thành công trong phiên này |
| 5.1–5.3 Thực nghiệm, kiểm thử | tests/, docs/qa-v13-junit.xml, ml/models/*metrics.json | Phân biệt test logic/API, thực nghiệm từ khóa và đánh giá AI/HS chưa thực hiện |
| 5.4 Hạn chế | docs/QA_V13.md | Chưa kiểm định phát âm trẻ em, hiệu quả học tập, tải đồng thời hay phiên Live thật |

Khi viết báo cáo: chỉ mô tả chức năng đã xây dựng và nêu riêng phần chưa kiểm chứng; không ghi “đạt toàn bộ mục tiêu”, “đánh giá chính xác âm vị”, “CNN đã huấn luyện” hay “cloud đã triển khai” với minh chứng hiện có.
