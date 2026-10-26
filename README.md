# PHÁT THANH AI

Ứng dụng Windows chạy local để chuyển ảnh hoặc PDF thông báo tiếng Việt thành MP3 phục vụ truyền thanh. Luồng sử dụng là: **ảnh JPG/PNG/PDF → đọc chữ/OCR → cán bộ chỉnh sửa/xác nhận → VieNeu local → MP3**.

Ứng dụng không có đăng nhập, không có API key và không bật chia sẻ công khai. Giao diện HTML/CSS/JavaScript chạy local, chỉ bind tại `127.0.0.1`; ứng dụng ưu tiên cổng `7860` và tự dùng cổng trống đến `7870` nếu cần.

## Những gì bản MVP đã thực hiện

- Chọn nhiều ảnh JPG/PNG hoặc PDF theo thứ tự người dùng chọn. PDF có lớp chữ được đọc trực tiếp; PDF scan được render từng trang rồi OCR AI cục bộ.
- OCR AI dùng PaddleOCR để phát hiện dòng chữ và VietOCR Seq2Seq để nhận dạng tiếng Việt. Nếu model AI bị thiếu hoặc không khởi động được, ứng dụng tự chuyển sang Tesseract tiếng Việt và báo rõ trong phần cảnh báo.
- Mỗi PDF tối đa 50 MB và 50 trang để bảo đảm thời gian xử lý/RAM trên laptop mục tiêu; PDF đặt mật khẩu được báo rõ để người dùng thay bằng bản đã mở khóa.
- Tiền xử lý ảnh bảo thủ: sửa hướng EXIF, tăng tương phản, phóng ảnh nhỏ; giữ ảnh gốc nguyên vẹn.
- Hiển thị văn bản OCR theo từng trang ngay khi trang đó hoàn tất, để cán bộ có thể theo dõi tiến độ; không thể tạo MP3 trước khi đánh dấu đã kiểm tra nội dung.
- Tách `original_text` khỏi `speech_text`; chỉ chuẩn hóa khoảng trắng, `08h30` và `ngày 15/10/2026` khi ngữ cảnh rõ ràng. Mã hồ sơ, số điện thoại, chữ viết tắt và số mơ hồ không bị suy đoán.
- Chia bản tin dài ở ranh giới câu/từ, tạo từng WAV bằng VieNeu v3 Turbo CPU/ONNX, rồi ghép thành MP3 mono 128 kbps có khoảng nghỉ ngắn giữa đoạn.
- Lỗi OCR/TTS/FFmpeg trả thông báo tiếng Việt và không xóa nội dung đã sửa hay MP3 đầu ra.
- Runtime khóa `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`. Model bị thiếu sẽ báo lỗi thay vì tự tải.

## Cấu trúc

```text
app/
  ui/web.py                    # Máy chủ FastAPI cục bộ và API OCR/TTS
  ui/templates/, ui/static/    # Giao diện HTML/CSS/JavaScript thuần
  services/ocr_service.py      # Đọc PDF, OCR AI và Tesseract dự phòng
  services/ai_ocr_service.py   # PaddleOCR detection + VietOCR recognition
  services/text_processor.py   # original_text / speech_text
  services/tts_service.py      # VieNeu CPU offline
  services/audio_service.py    # FFmpeg -> MP3
  services/workflow.py         # Pipeline tạo bản tin
bin/
  tesseract/                   # Tesseract.exe + tessdata/vie.traineddata khi phát hành
  ffmpeg/                      # ffmpeg.exe khi phát hành
models/vieneu/huggingface/     # Cache VieNeu đã chuẩn bị trước khi đóng gói
models/ocr/                    # Paddle detector + trọng số VietOCR cục bộ
scripts/                       # Chuẩn bị model, kiểm tra offline, build
launcher.py                    # Điểm khởi động nhấp đúp
```

File tạm và MP3 được ghi vào thư mục dễ thấy `data\public data` trong dự án: file tạm ở `data\public data\temp`, MP3 ở `data\public data\output`, và log ở `data\public data\logs`. Có thể đổi toàn bộ vị trí này bằng biến môi trường `PHAT_THANH_AI_DATA_DIR`. File tạm cũ hơn 48 giờ được dọn lúc mở app; MP3 đầu ra không tự xóa.

## Chạy từ mã nguồn

Yêu cầu: Windows 10/11 64-bit, Python 3.10–3.13, CPU x64, và quyền ghi vào `%LOCALAPPDATA%`. Python 3.11 là cấu hình nên dùng cho máy đóng gói; máy hiện tại có Python 3.10 vẫn phù hợp với các package đã ghim.

1. Cài package Python (VieNeu được cài ở chế độ SDK, không kèm giao diện mẫu):

   ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    .\scripts\install_runtime.ps1 -Python .\.venv\Scripts\python.exe
    ```

2. Đặt các công cụ offline trong bundle:

   ```text
   bin/tesseract/tesseract.exe
   bin/tesseract/tessdata/vie.traineddata
   bin/ffmpeg/ffmpeg.exe
   ```

   Có thể dùng đường dẫn cài riêng bằng `TESSERACT_CMD` và `FFMPEG_CMD`, nhưng bản phát hành nên mang theo binary đã kiểm thử. Tesseract phải nhận ra ngôn ngữ `vie`.

3. Trên **máy staging có Internet**, chuẩn bị cache model một lần. Lệnh này có chủ đích tải model; ứng dụng chạy thường không chạy nó:

   ```powershell
   .\.venv\Scripts\python.exe scripts/prepare_offline_assets.py --allow-network
   ```

   Script nạp `pnnbao-ump/VieNeu-TTS-v3-Turbo`, tải PaddleOCR/VietOCR vào `models/ocr`, tạo WAV thử và xác nhận mọi model có thể được nạp từ thư mục dự án. Ứng dụng chạy thường không tự tải model.

4. Ngắt Wi-Fi/Ethernet và kiểm tra cache thực sự đủ:

   ```powershell
   .\.venv\Scripts\python.exe scripts/verify_offline.py
   ```

5. Chạy giao diện:

   ```powershell
   .\.venv\Scripts\python.exe launcher.py
   ```

   Trình duyệt mở tại `http://127.0.0.1:7860`. Không dùng `share=True`, không mở cổng LAN và không gửi ảnh/văn bản/audio lên dịch vụ bên ngoài.

## Kiểm thử

Các kiểm thử đơn vị không cần VieNeu, Tesseract hay FFmpeg:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Trước khi nghiệm thu, cần chạy thêm trên laptop mục tiêu với 50 ảnh theo kế hoạch và hoàn tất các kiểm tra sau:

- PaddleOCR/VietOCR hoạt động, ảnh/PDF trống báo lỗi rõ ràng, nhiều tệp vẫn giữ đúng thứ tự. Tesseract chỉ được dùng làm dự phòng khi OCR AI không khả dụng.
- PDF có lớp chữ được đọc không cần OCR; PDF scan nhiều trang giữ đúng thứ tự khi render và OCR.
- Cán bộ sửa được OCR và app chặn tạo audio khi chưa xác nhận.
- Bản tin dài không mất/đảo câu; nghe lại số liệu, ngày giờ và địa danh.
- MP3 phát được trên phần mềm hoặc thiết bị loa thực tế.
- Tắt Wi-Fi/Ethernet, chạy `verify_offline.py`, sau đó thực hiện đủ ảnh/PDF → OCR → MP3.
- Sao chép thư mục `dist\PhatThanhAI` sang laptop Windows sạch để chạy thử, không cài Python.

## Đóng gói Windows one-folder

Chỉ build sau khi đã có binary Tesseract/FFmpeg và cache VieNeu cục bộ trong đúng các thư mục nêu trên. Khi đó:

```powershell
.\scripts\build.ps1 -Clean
```

Kết quả là `dist\PhatThanhAI\PhatThanhAI.exe`. Đây là thư mục one-folder; không tách riêng `_internal`, `models` hay `bin` khỏi thư mục `PhatThanhAI` khi bàn giao. Có thể dùng Inno Setup để tạo shortcut Desktop sau khi kiểm thử bản thư mục này.

`installer.spec` kèm PaddlePaddle, PyTorch, PaddleOCR, VietOCR và model cục bộ nên bộ one-folder sẽ lớn hơn bản Tesseract-only. Không tách riêng `models/ocr` khỏi thư mục phát hành.

## Lưu ý vận hành và giới hạn POC

- Giọng mặc định là **Hải Đăng**. Việc chọn giọng chính thức chỉ nên chốt sau khi cán bộ nghe thử trên loa thật.
- Bản này chưa có đăng nhập, lịch sử nghiệp vụ, tự động phát lên loa, nhạc nền, cloud API hay nhân bản giọng.
- Tỷ lệ chính xác OCR và tốc độ không được cam kết bởi mã nguồn. Cần đo trên laptop đích và tập ảnh đã chốt.
- VieNeu và tài nguyên model/voice phải được rà soát điều khoản phân phối trước khi phát hành rộng. Repository VieNeu công bố Apache-2.0; trọng số và mọi binary đi kèm cần được kiểm tra riêng trong giai đoạn đóng gói.
- Danh mục license/NOTICE phải kèm bộ cài được theo dõi trong [licenses/THIRD_PARTY_NOTICES.md](licenses/THIRD_PARTY_NOTICES.md).

## Cơ sở tích hợp

VieNeu v3 Turbo hỗ trợ SDK chạy CPU qua ONNX, giọng preset và hàm `Vieneu(...).infer(...); save(...)`; ứng dụng dùng đúng đường tích hợp này và cưỡng chế `device="cpu"`. Tham khảo [tài liệu SDK VieNeu](https://github.com/pnnbao97/VieNeu-TTS#-2-using-the-python-sdk) và [repository VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS). Giao diện dùng FastAPI cùng HTML/CSS/JavaScript cục bộ; OCR được đẩy từng trang qua Server-Sent Events.
