# ATC Symposium Desk

created by Lộc đẹp trai

Bộ ứng dụng hội trường / hội thảo / khóa ICAO: nghe, dịch thuật ngữ ATM/ATS, đề xuất câu đáp English theo vai.

Một codebase cho **máy tính (PWA)** và **điện thoại (Capacitor — iOS + Android)**.

- Máy tính: Chrome/Edge Translator, dịch từng câu trên máy.
- Điện thoại native (APK/IPA): dịch **cả câu** bằng ML Kit trên máy. PWA trên điện thoại **không** dịch cả câu.

Không gọi Google Translate API, không gọi Whisper đám mây.

## Cài đặt trên máy tính (Windows) — 1 file

Copy **`phat-hanh/ATC-Desk.exe`** sang máy mới (USB, mạng nội bộ…). Double-click. Không cần Python, không cần bộ mã nguồn.

1. Lần đầu, EXE ghi giao diện + DB thư viện vào `%LOCALAPPDATA%\ATC-Symposium-Desk`.
2. Trình duyệt tự mở `http://127.0.0.1:8765`.
3. Giữ cửa sổ đen mở. Tắt: `Ctrl+C`.

Cùng một bản này phục vụ điện thoại trên cùng Wi-Fi (PWA). Nếu `ATC-Desk.apk` nằm **cùng thư mục** với EXE, điện thoại tải native APK tại `http://<IPv4>:8765/ATC-Desk.apk` (trang Cài máy). iOS native **không** đóng gói được trên Windows — cần Mac + Xcode; không có Mac thì ghim PWA HTTPS.

Máy đang có bộ mã nguồn: double-click **`CAI_DAT_VA_CHAY.cmd`** (hoặc `MO_APP.cmd`) — tự cài Python nếu thiếu rồi chạy. Đóng gói lại (EXE kèm DB + APK Android) vào `phat-hanh\`:

```
DONG_GOI.cmd
```

Hoặc từng phần:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\dong-goi-windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tools\dong-goi-apk.ps1
```

```
Máy này:              http://127.0.0.1:8765
Điện thoại (cài PWA): http://<IPv4>:8765/cai-dat.html
HTTPS:                https://<IPv4>:8766/
```

IPv4 LAN in ra trong cửa sổ khi app chạy. Máy tính và điện thoại phải **cùng Wi-Fi**.

## Cài đặt trên Android (dịch cả câu)

Dùng file APK đã đóng gói:

`phat-hanh/ATC-Desk.apk`

**Cách 1 — USB (tự cài khi bấm file chạy):**

1. Cắm điện thoại, bật **Gỡ lỗi USB**.
2. Double-click `CAI_DAT_VA_CHAY.cmd`.
3. App cài APK rồi mở trên điện thoại (đồng thời mở trên máy tính).

**Cách 2 — copy file:**

1. Copy `phat-hanh/ATC-Desk.apk` sang điện thoại.
2. Mở file → Cài (cho phép nguồn không rõ nếu máy hỏi).
3. Mở **ATC Desk**.

Lần đầu còn Wi-Fi: trong app bấm **Tải gói dịch EN+VI** (~60 MB). Hội trường: airplane mode, không cần laptop.

## Cài PWA trên điện thoại (chỉ glossary / câu đáp)

Safari/Chrome chỉ lưu PWA khi trang là **HTTPS**. Không có dịch cả câu — cần APK/IPA ở trên.

1. Máy tính đang chạy `ATC-Desk.exe` hoặc `CAI_DAT_VA_CHAY.cmd`.
2. Điện thoại cùng Wi-Fi, mở `http://<IPv4-máy-tính>:8765/cai-dat.html`.
3. Tải **ATC-Desk-CA.cer** và tin cậy chứng chỉ  
   (iOS: Cài đặt → Cài đặt chung → Giới thiệu → Cài đặt tin cậy chứng chỉ).
4. Mở `https://<IPv4-máy-tính>:8766/`.
5. **iPhone (Safari):** Chia sẻ → Thêm vào Màn hình chính.  
   **Android (Chrome):** menu → Cài đặt ứng dụng / Thêm vào màn hình chính.
6. Huy hiệu **ĐÃ LƯU MÁY** = đã cache. Tắt Wi-Fi, mở icon ATC Desk.

## Cài iOS native (cần Mac + Xcode)

Không compile được trên Windows.

```
npm install
npx cap sync ios
```

Trên Mac: `cd ios/App && pod install`, mở `ios/App/App.xcworkspace` (CocoaPods — ML Kit không hỗ trợ SPM). Deployment target ≥ 15.5. Chọn team ký, Run vào iPhone.

Quyền: Microphone + Speech Recognition (đã ghi trong Info.plist). Lần đầu: cùng nút tải gói EN+VI. Model nằm trên máy.

## Đóng gói lại APK (khi sửa mã)

Cần **JDK 17 hoặc 21** (Java 26 không build được). Trên máy này dùng JDK kèm theo repo:

```
JAVA_HOME = .jdk21/jdk-21.0.12+8
GRADLE_USER_HOME = .gradle-home
```

Trong PowerShell, từ thư mục dự án:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\dong-goi-apk.ps1
```

File ra: `phat-hanh/ATC-Desk.apk` (và bản debug `android/app/build/outputs/apk/debug/app-debug.apk`).

Hoặc từng bước (nhớ đặt `JAVA_HOME` trước):

```
npm install
npx cap sync android
npx cap open android
```

Trong Android Studio: Run lên máy USB, hoặc Build → Build APK.

## Vai

| Vai | Việc |
| --- | --- |
| Đại biểu | Intervention English hội nghị |
| Báo cáo viên | Trả lời Q&A |
| Chủ tọa | Điều hành phiên — không dùng “cleared to land” |
| Phiên dịch | Bám thuật ngữ, không thêm lập trường |

Mỗi lần phân tích có 4 lớp: bản dịch chuyên ngành → câu đầy đủ → 60–90 giây → talking points + glossary.

## Offline sau khi đã cài app native

| Việc | Mạng |
| --- | --- |
| Dịch cả câu EN↔VI (ML Kit) | Không, sau khi tải gói EN+VI một lần |
| Câu đáp + tra cứu + lập trường + TTS máy | Không cần |
| Nghe nói → chữ | Gói nhận giọng của máy (iOS Dictation / Android Speech Services offline) |

## Kiểm tra

### Thư viện Anh–Việt offline

Mở **Thuật ngữ** để tra cứu 12.780 mục bằng tiếng Anh, tiếng Việt có/không dấu hoặc viết tắt; lọc chuyên đề và câu mẫu. Thư viện gồm 11.953 mục phổ thông, 691 mục kế thừa và 136 mục bổ sung (dẫn đường, ATM/ATC, thuyết trình và hội nghị). Mỗi mục có nguồn, ghi chú ngữ cảnh và trạng thái đối chiếu. Phổ thông giữ nghĩa đầu từ dữ liệu có sẵn, chưa được thẩm định từng mục. Bản dịch biên soạn không phải bản dịch chính thức ICAO.

- `web/data/library.sqlite`: DB SQLite với bảng `entries`, `sources`, `metadata` và chỉ mục tìm kiếm `entries_fts` (FTS5).
- `web/data/library.json`: bản xuất có cùng dữ liệu; `web/js/library-data.js` là snapshot được app tải trực tiếp, không cần máy chủ DB.
- `data/conference-library.tsv`: dữ liệu bổ sung có thể chỉnh sửa; `python tools/build_library.py` tái tạo DB và snapshot, không tải dữ liệu mạng. Các file sinh tự động bị thay thế khi build; chỉnh TSV để giữ thay đổi.

Câu có trong thư viện được dịch trực tiếp EN↔VI và ưu tiên trước dịch máy. Câu ngoài thư viện vẫn dùng cơ chế dịch hiện có; DB từ điển không tự biến thành mô hình dịch mọi câu. Nguồn tham chiếu được ghi trong DB, việc mở website nguồn cần mạng. Thông tư 19/2017 được dùng để đối chiếu thuật ngữ cụ thể và được ghi rõ hết hiệu lực một phần, không khẳng định toàn bộ quy định còn hiện hành.

PWA cần mở app một lần qua localhost/HTTPS và chờ service worker lưu đủ tài nguyên trước khi ngắt mạng. Native cần đóng gói lại APK/IPA để nhận dữ liệu mới.

```sh
python tools/build_library.py
python tests/library_db_test.py
python tests/serve_paths_test.py
node tests/library.test.js
```

```
node tests/engine.test.js
```

## Thư mục

```
ATC-Symposium-Desk/
  CAI_DAT_VA_CHAY.cmd      ← máy có bộ mã: cài (nếu thiếu) rồi chạy
  MO_APP.cmd               ← cùng việc
  DONG_GOI.cmd             ← đóng gói EXE (kem DB) + APK vào phat-hanh\
  phat-hanh/ATC-Desk.exe   ← 1 file cho máy Windows mới (kèm DB)
  phat-hanh/ATC-Desk.apk   ← Android native; EXE đang chạy cũng phục vụ /ATC-Desk.apk
  ATC-Desk.spec            ← PyInstaller one-file
  package.json             ← Capacitor
  capacitor.config.json
  android/                 ← project Android
  ios/                     ← project iOS (build trên Mac)
  tools/chay.ps1
  tools/dong-goi-windows.ps1
  tools/dong-goi-apk.ps1
  tools/serve.py
  README.md
  web/                     ← UI dùng chung (Hội trường / Thuật ngữ / REDA)
  tests/
```
