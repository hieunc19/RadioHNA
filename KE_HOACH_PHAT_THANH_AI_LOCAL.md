# KẾ HOẠCH XÂY DỰNG PHẦN MỀM PHÁT THANH AI LOCAL

> **Dự án:** Chuyển đổi hình ảnh chứa văn bản thành giọng đọc phục vụ loa truyền thanh xã/phường  
> **Phiên bản kế hoạch:** 1.0  
> **Ngày lập:** 13/10/2026  
> **Mô hình:** Web Local – xử lý offline – không dùng Cloud API  
> **Đối tượng sử dụng:** Cán bộ phụ trách thông tin, văn hóa và truyền thanh xã/phường  
> **Trạng thái:** Kế hoạch triển khai, chưa phải phần mềm đã hoàn thiện

---

## I. MỤC TIÊU VÀ PHẠM VI

### 1. Mục tiêu tổng thể

Xây dựng công cụ đơn giản giúp cán bộ xã/phường chuyển ảnh chụp thông báo, văn bản hoặc tài liệu thành **một file âm thanh MP3 bằng giọng đọc tiếng Việt**, sử dụng trên hệ thống loa truyền thanh sẵn có.

Phần mềm chạy trực tiếp trên laptop của cán bộ. Người dùng nhấp đúp biểu tượng để khởi chạy giao diện trong trình duyệt tại địa chỉ Local (ví dụ `http://127.0.0.1:7860`). Toàn bộ OCR và TTS xử lý trên máy, không cần VPS, tên miền hay phí API. Internet có thể cần khi chuẩn bị bộ cài, nhưng **không được cần trong quá trình sử dụng sau khi cài đặt đầy đủ**.

**Luồng công việc cốt lõi:**

```text
Tải một hoặc nhiều ảnh
          ↓
Trích xuất văn bản (OCR)
          ↓
Cán bộ kiểm tra/chỉnh sửa nội dung
          ↓
Chuẩn hóa cách đọc và tạo giọng nói (VieNeu Local)
          ↓
Ghép âm thanh, chuyển thành MP3
          ↓
Nghe lại và lưu MP3 vào laptop
          ↓
Cán bộ chuyển MP3 sang hệ thống loa hiện có
```

> **Nguyên tắc nghiệp vụ:** Không tự động phát thanh ngay sau khi OCR. Cán bộ cần xác nhận văn bản, nghe lại file MP3 trước khi phát. Hệ thống không được tự ý viết lại nội dung hành chính làm thay đổi ý nghĩa.

### 2. Chức năng phải có trong MVP

| Mã | Chức năng | Yêu cầu |
|---|---|---|
| F01 | Tải hình ảnh | Một hoặc nhiều ảnh JPG/PNG; giữ đúng thứ tự trang |
| F02 | Nhận diện văn bản | OCR tiếng Việt, thông báo khi ảnh không có chữ hoặc chất lượng kém |
| F03 | Kiểm tra và chỉnh sửa | Hiển thị toàn bộ nội dung OCR trong ô cho phép chỉnh sửa |
| F04 | Chuẩn hóa cách đọc | Dấu cách, dấu câu, một số định dạng ngày giờ/số đã kiểm thử; giữ các trường hợp mơ hồ để cán bộ kiểm tra |
| F05 | Chuyển thành giọng đọc | VieNeu chạy bằng CPU hoàn toàn tại máy; một giọng phát thanh mặc định được chọn sau khi kiểm thử |
| F06 | Nghe lại | Trình phát audio ngay trên giao diện |
| F07 | Xuất âm thanh | Ghép các đoạn và lưu thành một file MP3 hoàn chỉnh |

**Ngoài phạm vi phiên bản 1.0:** đăng ký/đăng nhập, phân quyền đa đơn vị, dashboard, cơ sở dữ liệu nghiệp vụ, lưu lịch sử dài hạn, nhân bản giọng, thu âm trực tiếp, ứng dụng di động riêng, kết nối/phát trực tiếp lên thiết bị loa, Cloud API, VPS, tên miền và hệ thống microservice.

### 3. Nguyên tắc thiết kế

- Một màn hình làm việc, thao tác dễ hiểu đối với cán bộ không chuyên CNTT.
- Một máy tính có thể chạy độc lập, không yêu cầu GPU rời.
- Không gửi hình ảnh, văn bản hoặc audio tới máy chủ bên ngoài.
- Ưu tiên mã nguồn mở và tận dụng laptop hiện có; không đánh đồng **không có phí thuê bao** với **không có chi phí phát triển, điện năng, hỗ trợ**.
- Phần mềm phải xử lý được lỗi từng ảnh/từng đoạn audio và cho phép thử lại mà không làm mất nội dung đã chỉnh sửa.
- Không xây dựng chức năng không cần thiết trước khi kiểm chứng hiệu quả trên laptop thật.

---

## II. KIẾN TRÚC VÀ CÔNG NGHỆ

### 1. Kiến trúc tổng thể

```text
┌──────────────────────────────────────────────────────────┐
│                   LAPTOP CỦA CÁN BỘ                     │
│                   Windows 10/11 64-bit                   │
│                                                          │
│   PhatThanhAI.exe (launcher)                              │
│              │                                           │
│              ▼                                           │
│   FastAPI Web Local: http://127.0.0.1:7860                │
│              │                                           │
│              ▼                                           │
│   Python Application                                     │
│      ├── Image Processing (Pillow/OpenCV)                 │
│      ├── Tesseract OCR + dữ liệu tiếng Việt               │
│      ├── Text Processing                                  │
│      ├── VieNeu v3 Turbo CPU/ONNX                         │
│      └── FFmpeg: ghép WAV / xuất MP3                      │
│              │                                           │
│              ▼                                           │
│       ban_tin_phat_thanh.mp3                              │
└──────────────────────────────────────────────────────────┘

Không có kết nối bắt buộc tới VPS hoặc Cloud API.
```

### 2. Công nghệ lựa chọn

| Thành phần | Công nghệ đề xuất | Vai trò |
|---|---|---|
| Ngôn ngữ | Python 3.11 (64-bit), sau khi xác nhận tương thích SDK | Ứng dụng và nghiệp vụ |
| Giao diện | FastAPI + HTML/CSS/JavaScript | Web Local một màn hình |
| OCR | Tesseract OCR + `vie.traineddata` | Nhận diện chữ tiếng Việt |
| Tiền xử lý ảnh | Pillow, OpenCV | Chỉnh hướng, tăng tương phản khi cần |
| TTS chính | VieNeu v3 Turbo (CPU/ONNX) | Tạo giọng đọc tiếng Việt offline |
| Phương án dự phòng | VieNeu v3 Nano | Thử khi Turbo không đáp ứng hiệu năng |
| Audio | FFmpeg | Ghép đoạn, xuất MP3 |
| Đóng gói | PyInstaller chế độ One-folder | Phân phối môi trường chạy Windows |
| Trình cài đặt (tùy chọn) | Inno Setup | Shortcut và quy trình cài đặt đơn giản |
| Lưu dữ liệu | Thư mục tạm và output trong hồ sơ người dùng | Không cần MySQL/Redis |

**Lưu ý tích hợp:** Ưu tiên dùng SDK VieNeu chính thức, khóa phiên bản phụ thuộc sau khi thử nghiệm thành công. Tránh sửa trực tiếp mã nguồn engine nếu không bắt buộc. Phải kiểm tra giấy phép của cả mã nguồn, trọng số mô hình, các giọng mẫu và thư viện đi kèm trước khi phân phối bộ cài.

### 3. Cấu hình laptop mục tiêu (đề xuất, cần đo thực tế)

| Thành phần | Mục tiêu |
|---|---|
| Hệ điều hành | Windows 10/11 64-bit |
| CPU | Core i5 thế hệ 10 trở lên hoặc tương đương; ưu tiên thử máy i5 thế hệ 12 |
| RAM | Khuyến nghị 16GB; máy 8GB chỉ đưa vào diện kiểm thử |
| Lưu trữ | SSD, dự trù 15–20GB dung lượng trống cho môi trường chạy, mô hình và file tạm |
| GPU | Không bắt buộc |
| Internet | Không cần sau khi bộ cài đã có đủ mô hình/tài nguyên |

Không cam kết tốc độ từ benchmark của nhà phát triển thay cho tốc độ đo trên laptop đích. Nếu chạy CPU INT8, chỉ kích hoạt sau khi xác nhận CPU và mô hình tương thích; giữ chế độ ổn định làm mặc định.

---

## III. ĐẶC TẢ CÁC MODULE

### 1. Module Image Processing và OCR

**Đầu vào:** Một hoặc nhiều file ảnh JPG/PNG.

**Các bước:**

1. Kiểm tra phần mở rộng, nội dung file và giới hạn kích thước phù hợp.
2. Lưu ảnh vào thư mục tạm cục bộ, không tải lên Internet.
3. Kiểm tra hướng ảnh, xoay/cải thiện tương phản nếu cần; giữ bản ảnh gốc để đối chiếu.
4. Gọi Tesseract OCR với dữ liệu tiếng Việt.
5. Ghép kết quả theo thứ tự ảnh người dùng đã chọn.
6. Hiển thị văn bản trong ô chỉnh sửa.

**Yêu cầu lỗi:** Nếu ảnh không đọc được, báo rõ ảnh nào gặp lỗi, cho phép thay ảnh hoặc nhập/sửa thủ công; không tạo văn bản giả. Ảnh nhiều cột hoặc có bố cục phức tạp phải được đưa vào tập kiểm thử. Chỉ thay Tesseract bằng OCR nặng hơn nếu dữ liệu kiểm thử chứng minh cần thiết.

### 2. Module kiểm tra và chuẩn hóa văn bản

Duy trì ít nhất hai biến tách biệt:

```python
original_text = ""  # Nội dung OCR đã được cán bộ chỉnh sửa/xác nhận
speech_text = ""    # Bản dùng để tổng hợp tiếng nói sau chuẩn hóa
```

Quy tắc xử lý ưu tiên: loại bỏ khoảng trắng thừa, sửa xuống dòng không hợp lý theo các quy tắc an toàn, chuẩn hóa dấu câu và các biểu thức giờ/ngày rõ ngữ cảnh. Với số điện thoại, ký hiệu hồ sơ, tên riêng, chữ viết tắt hoặc địa điểm có khả năng nhập nhằng, không tự ý suy đoán; người dùng kiểm tra trước khi chuyển đổi.

**Ví dụ:** `08h30 ngày 15/10/2026` có thể chuyển sang cách đọc tự nhiên sau khi quy tắc đã được kiểm thử. Không thay đổi ý nghĩa của một thông báo chỉ để giọng đọc trôi chảy hơn.

### 3. Module VieNeu TTS

- Chạy engine tại máy qua CPU/ONNX; không gọi VieNeu Cloud API.
- Chọn một giọng đọc phát thanh mặc định sau khi nghe thử với cán bộ; chưa cần bộ chọn hàng chục giọng.
- Kiểm thử một bản tin ngắn trước, sau đó bản tin dài.
- Chia văn bản dài theo câu/đoạn, tránh cắt giữa ngày tháng, tên riêng hoặc câu chưa hoàn chỉnh.
- Sinh audio từng đoạn theo đúng thứ tự; có thể xử lý lại đoạn lỗi mà không mất văn bản gốc.
- Sử dụng phiên bản SDK/API đã ghim và kiểm tra lại tên giọng, tham số, đường dẫn mô hình trực tiếp trên môi trường cài đặt; mã ví dụ không thay thế kiểm thử tích hợp.
- Tài nguyên model/voice phải có sẵn cục bộ, không âm thầm tải khi thiếu cache.

**Tiêu chí chất lượng:** âm thanh rõ, không mất câu, không đảo đoạn; cần nghe kiểm tra các mục có số liệu, ngày giờ và địa danh. Chưa cần nhân bản giọng người thật.

### 4. Module Audio/MP3

```text
WAV đoạn 1 + WAV đoạn 2 + ...
             ↓
Sắp xếp đúng thứ tự và chèn khoảng nghỉ phù hợp
             ↓
Ghép/chuẩn hóa mức âm lượng khi cần
             ↓
FFmpeg → ban_tin_phat_thanh.mp3
```

Cấu hình MP3 thử nghiệm: mono, 128 kbps. Phải xác nhận thiết bị phát thanh thực tế của đơn vị phát được định dạng đầu ra. Chưa đưa nhạc nền, hiệu ứng hay nhạc mở/kết vào MVP.

### 5. Launcher và dữ liệu cục bộ

- Người dùng mở `PhatThanhAI.exe` bằng cách nhấp đúp.
- Launcher khởi động chương trình nội bộ, mở Chrome/Edge đến `http://127.0.0.1:7860` (hoặc cổng cục bộ được cấu hình hợp lệ).
- Chỉ bind trên địa chỉ loopback `127.0.0.1`, không bật `share=True`.
- Thư mục output và temp nên đặt trong vùng dữ liệu có quyền ghi của tài khoản Windows, không phụ thuộc quyền ghi vào `Program Files`.
- Có chính sách dọn file tạm, không xóa MP3 người dùng đã chủ động lưu.

---

## IV. THIẾT KẾ GIAO DIỆN MỘT TRANG

**Tên hiển thị đề xuất:** PHÁT THANH AI – Tạo bản tin truyền thanh từ hình ảnh.

```text
┌────────────────────────────────────────────┐
│ PHÁT THANH AI                              │
├────────────────────────────────────────────┤
│ 01. CHỌN ẢNH VĂN BẢN                       │
│ [Tải một/nhiều ảnh JPG, PNG]               │
│ [NHẬN DIỆN VĂN BẢN]                        │
├────────────────────────────────────────────┤
│ 02. KIỂM TRA NỘI DUNG                      │
│ [Ô văn bản OCR có thể chỉnh sửa           ]│
│ Lưu ý: kiểm tra ngày, giờ, địa danh...      │
├────────────────────────────────────────────┤
│ 03. TẠO GIỌNG ĐỌC                          │
│ Giọng phát thanh mặc định                  │
│ [TẠO FILE ÂM THANH]   [Tiến độ xử lý]       │
├────────────────────────────────────────────┤
│ 04. BẢN TIN HOÀN THÀNH                     │
│ [▶ Nghe lại]                               │
│ [TẢI FILE MP3]                             │
└────────────────────────────────────────────┘
```

**Quy tắc giao diện:**

- Một trang, không chuyển màn hình hoặc yêu cầu tạo tài khoản.
- Chỉ cho tạo audio khi có nội dung đã được người dùng kiểm tra/xác nhận.
- Hiển thị tiến độ xử lý và lỗi bằng tiếng Việt dễ hiểu.
- Khi tạo audio lỗi, không làm mất ảnh hoặc văn bản đã sửa.
- Kết quả tải về là một file MP3 hoàn chỉnh; tên file dễ nhận biết.
- Không thêm tùy chọn cấu hình kỹ thuật phức tạp vào giao diện người dùng cuối.

---

## V. CẤU TRÚC MÃ NGUỒN ĐỀ XUẤT

```text
PHAT-THANH-AI/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── ui/
│   │   └── interface.py
│   ├── services/
│   │   ├── image_processor.py
│   │   ├── ocr_service.py
│   │   ├── text_processor.py
│   │   ├── tts_service.py
│   │   └── audio_service.py
│   └── utils/
│       ├── file_helper.py
│       └── validators.py
│
├── assets/
│   ├── icon/
│   └── voices/
├── models/
│   └── vieneu/
├── bin/
│   ├── tesseract/
│   └── ffmpeg/
├── data/
│   ├── temp/
│   └── output/
├── tests/
│   ├── test_ocr.py
│   ├── test_text.py
│   ├── test_tts.py
│   └── test_offline.py
├── launcher.py
├── requirements.txt
├── installer.spec
└── README.md
```

| File | Nhiệm vụ |
|---|---|
| `main.py` | Khởi chạy phần mềm |
| `web.py` | Máy chủ FastAPI và giao diện HTML/CSS/JavaScript |
| `image_processor.py` | Tiền xử lý hình ảnh |
| `ocr_service.py` | Nhận diện chữ tiếng Việt |
| `text_processor.py` | Làm sạch và chuẩn hóa nội dung đọc |
| `tts_service.py` | Gọi VieNeu Local |
| `audio_service.py` | Ghép WAV, chuyển MP3 |
| `launcher.py` | Khởi động Local Web và mở trình duyệt |
| `config.py` | Thông số giọng đọc, mô hình, thư mục |

> Đây là cấu trúc **source**. Bộ cài phát hành có thể bố trí khác, đặc biệt thư mục dữ liệu người dùng sẽ nằm ở nơi Windows cho phép ghi.

---

## VI. LỘ TRÌNH TRIỂN KHAI

**Thời lượng lập kế hoạch:** 15–18 ngày làm việc với một lập trình viên Python có hỗ trợ kiểm thử/điều phối. Đây là dự toán, phụ thuộc việc VieNeu hoạt động ổn định trên laptop mục tiêu và việc đóng gói Windows.

| Giai đoạn | Thời điểm dự kiến | Công việc | Đầu ra |
|---|---|---|---|
| 1. POC công nghệ | Ngày 1–3 | Cài và thử VieNeu CPU, Tesseract trên laptop thật; đo RAM/tốc độ | WAV tiếng Việt và OCR từ ảnh offline |
| 2. Module xử lý | Ngày 4–7 | Hoàn thiện Image/OCR/Text/TTS/Audio, ghép MP3 | Pipeline Python ảnh → MP3 |
| 3. Web Local | Ngày 8–10 | Xây UI HTML/CSS/JavaScript với FastAPI; nối các module; xử lý tiến độ/lỗi | Giao diện dùng được một trang |
| 4. Đóng gói Windows | Ngày 11–14 | Đưa đủ runtime, model, OCR, FFmpeg vào gói; tạo launcher | Bộ chương trình chạy trên máy khác |
| 5. Kiểm thử và bàn giao | Ngày 15–18 | Chạy thử bằng ảnh thực tế; kiểm thử offline, âm thanh và tương thích loa | Bản 1.0 + tài liệu + biên bản |

### Danh mục giao việc

| Mã | Hạng mục | Đầu ra cần bàn giao |
|---|---|---|
| CV01 | Khảo sát laptop và dữ liệu thực tế | Bộ ảnh mẫu, cấu hình máy mục tiêu |
| CV02 | VieNeu Local | Module TTS, benchmark trên CPU |
| CV03 | OCR tiếng Việt | Module OCR, báo cáo tỷ lệ nhận diện |
| CV04 | Text Processing | Quy tắc chuẩn hóa và bài test |
| CV05 | Audio | Một MP3 ghép đúng thứ tự |
| CV06 | Giao diện | Web Local HTML/CSS/JavaScript |
| CV07 | Packaging | Bộ cài/chương trình offline Windows |
| CV08 | Kiểm thử | Báo cáo kết quả, danh sách lỗi đã xử lý |
| CV09 | Tài liệu | Hướng dẫn sử dụng, cài đặt và bảo trì |

### Mốc quyết định sau POC

Chỉ chuyển sang xây giao diện khi trả lời được ba câu hỏi:

1. VieNeu Turbo chạy được và có tốc độ chấp nhận được trên laptop mục tiêu hay không?
2. Tesseract có nhận diện đủ tốt ảnh thông báo thực tế, đặc biệt dấu tiếng Việt và thứ tự trang hay không?
3. Toàn bộ chuỗi ảnh → OCR → giọng đọc → MP3 có hoạt động khi ngắt Internet hay không?

Nếu Turbo không đáp ứng, kiểm thử Nano hoặc điều chỉnh cấu hình trước khi triển khai tiếp. Nếu Tesseract không đạt, so sánh công nghệ OCR khác trên **cùng bộ ảnh**, không thay đổi theo cảm tính.

---

## VII. KIỂM THỬ VÀ TIÊU CHÍ NGHIỆM THU

### 1. Bộ dữ liệu kiểm thử tối thiểu

| Loại ảnh | Số lượng |
|---|---:|
| Văn bản thông báo hành chính | 15 |
| Ảnh văn bản chụp từ điện thoại | 15 |
| Thông báo nhiều số liệu/ngày tháng | 10 |
| Văn bản nhiều trang | 5 |
| Ảnh mờ, nghiêng hoặc chất lượng thấp | 5 |
| **Tổng cộng** | **50** |

Trong giai đoạn đầu, dùng 10 ảnh đại diện để kiểm tra POC; mở rộng đủ 50 ảnh trước nghiệm thu.

### 2. Tiêu chí nghiệm thu mục tiêu

| Nội dung | Mục tiêu cần đo |
|---|---|
| Khởi động | Cán bộ nhấp đúp icon, không phải nhập lệnh Python |
| OCR | Mục tiêu ≥95% ký tự đúng trên tập ảnh in rõ nét được chốt trước |
| Kiểm tra văn bản | Có thể xem và sửa đầy đủ nội dung trước khi tạo tiếng |
| TTS | Giọng rõ, không mất câu/đảo đoạn |
| Thời gian xử lý | Phấn đấu tạo bản tin 5 phút trong ≤5 phút trên laptop mục tiêu; xác nhận bằng đo thực tế |
| MP3 | Phát được trên thiết bị loa/phần mềm phát thanh của đơn vị |
| Offline | Ngắt Internet vẫn OCR, tạo audio và tải MP3 được |
| Ổn định | Lỗi một ảnh/đoạn không xóa nội dung đã sửa |
| Riêng tư | Không tự gửi ảnh, chữ, audio ra máy chủ bên ngoài |

> Các con số trên là **mục tiêu nghiệm thu đề xuất**, không phải cam kết đã đo được. Ngay cả khi tỷ lệ OCR tổng thể đạt, mọi ngày tháng, tên riêng, địa danh, số liệu quan trọng vẫn cần cán bộ rà soát trước khi phát thanh.

### 3. Tình huống kiểm thử bắt buộc

- [ ] Ảnh không chứa chữ → thông báo rõ ràng.
- [ ] Ảnh xoay ngang → xử lý hướng hoặc cho phép thay ảnh.
- [ ] Nhiều ảnh → văn bản và audio giữ đúng thứ tự.
- [ ] OCR sai → người dùng chỉnh sửa được.
- [ ] TTS không đủ RAM/thất bại giữa chừng → không làm mất nội dung.
- [ ] Đoạn audio lỗi → có cách thử lại.
- [ ] Đóng trình duyệt rồi chạy lại launcher → dùng được.
- [ ] Ngắt Wi-Fi và Ethernet → chương trình vẫn xử lý hoàn toàn tại máy.
- [ ] Sao chép bộ chương trình sang một laptop Windows sạch → không yêu cầu cài Python thủ công hoặc tải mô hình ngoài.
- [ ] MP3 đầu ra phát được trên hệ thống phát thanh thực tế.

---

## VIII. ĐÓNG GÓI VÀ BÀN GIAO

### 1. Phương án đóng gói

Ưu tiên PyInstaller chế độ **One-folder**, không cố đưa toàn bộ trọng số AI vào một EXE duy nhất. Có thể bọc bộ chương trình trong Inno Setup để tạo trình cài và biểu tượng Desktop. Thực hiện trên môi trường Windows tương thích mục tiêu.

**Bộ phát hành dự kiến:**

```text
PHAT-THANH-AI-v1.0/
├── PhatThanhAI.exe
├── _internal/          # Runtime Python và các thư viện
├── models/             # Trọng số VieNeu, tài nguyên giọng đã chuẩn bị
├── OCR/                # Tesseract và dữ liệu tiếng Việt
├── tools/              # FFmpeg
├── licenses/           # Giấy phép/NOTICE của các thành phần
└── Huong_Dan_Su_Dung.pdf
```

**Điều kiện offline:** Mọi model, voice resource và cache thiết yếu phải hiện diện trong gói. Cấu hình đường dẫn cục bộ rõ ràng; không để SDK âm thầm tải trọng số từ Hugging Face trong lần đầu sử dụng. Kiểm chứng trên máy sạch và đã ngắt mạng.

**An toàn:** chỉ mở cổng trên `127.0.0.1`, không bật chế độ public share, không lưu API key Cloud (vì không dùng Cloud). Tạo bản checksum SHA-256 của bộ phát hành sau nghiệm thu để kiểm tra khi sao chép sang các đơn vị khác.

### 2. Danh mục bàn giao

| STT | Sản phẩm | Định dạng |
|---|---|---|
| 1 | Mã nguồn dự án | Python project |
| 2 | Bộ cài/bộ chương trình Windows | Installer hoặc thư mục One-folder |
| 3 | Mô hình VieNeu Local và tài nguyên cần thiết | Bộ model đã kiểm tra giấy phép |
| 4 | Tesseract và dữ liệu tiếng Việt | Bộ OCR offline |
| 5 | Hướng dẫn sử dụng | PDF |
| 6 | Hướng dẫn cài đặt và bảo trì | PDF/Markdown |
| 7 | Bộ ảnh kiểm thử | Thư mục mẫu |
| 8 | Báo cáo kiểm thử/biên bản nghiệm thu | PDF/Markdown |
| 9 | Thông tin phiên bản và SHA-256 bộ cài | TXT |

---

## IX. CHI PHÍ VÀ RỦI RO

### 1. Nguyên tắc chi phí

| Hạng mục | Chi phí thuê bao dự kiến |
|---|---:|
| VieNeu v3 Turbo mã nguồn mở | Không trả phí Cloud API; cần tuân thủ giấy phép tương ứng |
| Tesseract OCR | 0đ phí phần mềm |
| Python/FastAPI | 0đ phí phần mềm |
| VPS/domain | Không cần |
| GPU riêng | Không mua ở bản đầu |
| Laptop | Tận dụng máy hiện có |
| Phí tạo từng bản tin | Không có phí API theo lượt |

Vẫn có chi phí nhân lực phát triển, điện năng, lưu trữ, hỗ trợ cài đặt và bảo trì; không ghi tổng chi phí dự án là 0đ nếu các hạng mục này cần hạch toán.

### 2. Rủi ro và biện pháp

| Rủi ro | Mức độ | Biện pháp |
|---|---|---|
| OCR sai ngày tháng/tên riêng | Cao | Luôn cho kiểm tra, sửa nội dung trước TTS |
| VieNeu CPU chậm trên laptop cũ | Cao | POC trên máy thật, cân nhắc Nano nếu cần |
| Bộ cài thiếu model/cache, vẫn đòi Internet | Cao | Kiểm thử trên laptop sạch đã ngắt mạng |
| Lỗi packaging do thư viện/model | Cao | Khóa dependencies, dùng One-folder, đóng gói trên Windows |
| Bản tin dài lỗi giữa chừng | Trung bình | Chia đoạn, lưu trạng thái, thử lại đoạn lỗi |
| File MP3 không tương thích thiết bị loa | Trung bình | Kiểm thử trực tiếp trên hệ thống phát thanh của đơn vị |
| Lộ văn bản qua cổng web nội bộ | Trung bình | Bind loopback, tắt public share, không gọi API ngoài |
| Vấn đề giấy phép khi phân phối | Trung bình | Rà soát mã nguồn, model, giọng mẫu và thư viện; kèm LICENSE/NOTICE cần thiết |

---

## X. CHECKLIST KHỞI ĐỘNG DỰ ÁN

- [ ] Chuẩn bị laptop Windows RAM 16GB làm máy kiểm thử chuẩn.
- [ ] Thu thập 10 ảnh thông báo thực tế để thử POC.
- [ ] Kiểm tra giấy phép và cài đặt VieNeu SDK chạy CPU/ONNX.
- [ ] Khóa phiên bản Python và các thư viện sau khi chạy ổn định.
- [ ] Tạo thử audio tiếng Việt từ đoạn khoảng 2.000 ký tự.
- [ ] Nghe thử tối thiểu hai giọng phù hợp bản tin phát thanh.
- [ ] Ghi nhận thời gian xử lý và mức RAM thực tế.
- [ ] Cài Tesseract và `vie.traineddata`.
- [ ] Chạy OCR và đối chiếu độ chính xác trên 10 ảnh mẫu.
- [ ] Kết nối ảnh → OCR → kiểm tra/sửa → TTS → MP3.
- [ ] Ngắt Internet, bảo đảm pipeline vẫn chạy hoàn chỉnh.
- [ ] Chỉ khi POC đạt mới làm giao diện một trang.
- [ ] Đóng gói và kiểm thử bộ cài trên laptop Windows sạch.
- [ ] Thử phát MP3 qua phần mềm/thiết bị loa truyền thanh thực tế.

---

## XI. NGUYÊN TẮC CHỐT PHIÊN BẢN 1.0

Chỉ nghiệm thu khi đồng thời đáp ứng ba điều kiện:

1. Cán bộ **nhấp đúp biểu tượng** và sử dụng được qua trình duyệt, không cần nhập lệnh.
2. Khi laptop **ngắt Internet**, phần mềm vẫn đọc ảnh, trích xuất chữ, tạo và xuất MP3.
3. Cán bộ được **kiểm tra văn bản và nghe lại âm thanh** trước khi chuyển file sang hệ thống loa.

Không mở rộng thêm chức năng trong giai đoạn đầu. Sau khi bộ cài chạy ổn định trên một vài laptop đại diện tại một xã/phường, mới xem xét nhân rộng.

---

## XII. TÀI LIỆU THAM KHẢO

- VieNeu – Tài liệu chính thức: https://docs.vieneu.io/vi/docs/
- VieNeu-TTS – Repository: https://github.com/pnnbao97/VieNeu-TTS
- Tesseract OCR: https://github.com/tesseract-ocr/tesseract
- Tesseract tessdata: https://github.com/tesseract-ocr/tessdata
- FastAPI Documentation: https://fastapi.tiangolo.com/
- PyInstaller Documentation: https://pyinstaller.org/en/stable/
- FFmpeg: https://ffmpeg.org/
- Inno Setup: https://jrsoftware.org/isinfo.php

*Ghi chú: Các lựa chọn về hiệu năng, mức độ chính xác và định dạng âm thanh là mục tiêu kỹ thuật cần xác nhận qua POC trên laptop và thiết bị phát thanh thực tế.*
