# Thư viện biên dịch hội nghị

Nguồn chỉnh sửa: `conference-library.tsv`, `vatm-terminology.tsv`, `doc4444-phraseology.tsv`, `vn-taxiways.tsv`, `vn-callsigns.tsv` (UTF-8, tab-separated). Mỗi dòng gồm domain, abbr, en, vi, note, source. Không sửa trực tiếp file SQLite/JSON/JS sinh tự động. Chạy `python tools/build_library.py` từ thư mục gốc sau khi sửa TSV. `tools/extract_vn_ops.py` dựng lại taxiway từ cache AIP local. Callsign hãng: `python tools/import_airline_db.py` đọc `Database_hang_hang_khong_ATC_Vietnam_2026.xlsx` rồi ghi `vn-airline-spoken.tsv` + `vn-callsigns.tsv`.

Domain: editor, phraseology, callsign, taxiway, navigation, atc, atm, conference, aviation_sentence. `legacy` và `general` được nhập từ dữ liệu có sẵn. Cùng từ có thể có nhiều nghĩa/ngữ cảnh; không xóa khác biệt nghĩa bằng cách gộp theo riêng từ tiếng Anh. ID được tạo ổn định từ cặp Anh–Việt và domain. Mẫu Editor lưu `data/user-phraseology.json` (máy này) và IndexedDB.

Nguồn `vn19` chỉ áp dụng cho ba mục PBN/RNP/RNAV đã đối chiếu Điều 3. Nguồn `pbn` cho khái niệm giám sát tính năng/cảnh báo trên tàu bay; bản dịch biên soạn. Nguồn `doc4444` là huấn lệnh / phraseology vô tuyến rút từ ICAO Doc 4444 Chapter 12 (kèm từ chuẩn Annex 10 Vol II); bản dịch tiếng Việt theo cách dùng VATM, không phải toàn văn tài liệu ICAO. Các mục khác không tự động được coi là thuật ngữ pháp lý đã thẩm định. Trạng thái `referenced` nghĩa là đã tham chiếu nguồn, không phải được cơ quan có thẩm quyền phê duyệt.

SQLite là DB độc lập; ứng dụng dùng snapshot JS có cùng nội dung để hoạt động không cần dịch vụ DB hay WebAssembly. FTS lưu văn bản chuẩn hóa không dấu, gồm chuyển đ thành d. Dùng JOIN với entries để trả văn bản gốc:

```sql
SELECT e.en, e.vi, e.abbr, e.note, s.title
FROM entries_fts f
JOIN entries e ON e.id = f.id
JOIN sources s ON s.id = e.source
WHERE entries_fts MATCH '"dan duong"';
```

Kiểm chứng 2026-09-11: SQLite integrity/foreign keys, FTS không dấu và parity JSON đạt; 41 câu biên soạn dịch hai chiều đạt; bộ engine hiện có đạt khi nạp thư viện mới. Trình duyệt tải lại từ service worker khi máy chủ kiểm thử đã tắt: 12.780 mục, DB tải từ cache 3.317.760 byte; yêu cầu URL chưa cache thất bại như dự kiến. Chưa đóng gói/kiểm thử APK hoặc IPA mới.

Kiểm chứng 2026-09-12: thêm `doc4444-phraseology.tsv` (459 mục huấn lệnh Doc 4444 Ch.12 / Annex 10 Vol II). Thư viện 13.616 mục; domain `phraseology` tra được CLEARED TO LAND, LINE UP AND WAIT, GO AROUND và FTS không dấu “vao duong chc” / “duoc phep ha canh”.
