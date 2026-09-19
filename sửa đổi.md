# ĐỀ XUẤT VÀ HƯỚNG DẪN THIẾT KẾ ỨNG DỤNG NHẬN DẠNG HỘI THOẠI ATC

## 1. Giới thiệu

Tài liệu này đề xuất kiến trúc và hướng dẫn thiết kế một ứng dụng hỗ trợ:

* Nghe hội thoại giữa **phi công và Kiểm soát viên không lưu (ATCO)**.
* Nhận dạng tiếng nói thành văn bản theo thời gian thực.
* Phân tích nội dung huấn lệnh kiểm soát không lưu.
* Nhận dạng callsign, mực bay, hướng bay, tốc độ, đường cất hạ cánh, tần số, mã SSR và các thành phần nghiệp vụ khác.
* Theo dõi và đối chiếu **clearance ↔ readback**.
* Phát hiện các trường hợp readback thiếu hoặc có sai khác.
* Ghi âm, lưu transcript và dữ liệu phân tích.
* Cho phép tìm kiếm và phát lại hội thoại theo thời gian, callsign hoặc loại huấn lệnh.
* Phân tích trực tiếp tín hiệu audio thời gian thực hoặc gián tiếp từ file/băng ghi âm.

Hệ thống được định hướng là **công cụ hỗ trợ ATCO, giám sát, huấn luyện và phân tích**, không thay thế việc xác nhận và ra quyết định nghiệp vụ của con người.

---

# 2. Mục tiêu hệ thống

Ứng dụng có hai chế độ hoạt động chính.

## 2.1. LIVE MODE

Nhận trực tiếp tín hiệu từ:

* VHF radio.
* VCS – Voice Communication System.
* Line-in audio.
* Audio gateway.
* Recording system.
* PTT system hoặc nguồn audio được phép tích hợp.

Sau đó thực hiện:

```text
Audio
 ↓
Audio Processing
 ↓
Speech Recognition
 ↓
ATC Semantic Analysis
 ↓
Clearance Detection
 ↓
Readback Matching
 ↓
Realtime User Interface
```

Mục tiêu là hiển thị transcript và dữ liệu nghiệp vụ gần thời gian thực.

---

## 2.2. RECORDING MODE

Nhận file như:

```text
WAV
MP3
FLAC
OGG
M4A
```

Sau đó:

```text
Recorded Audio
      ↓
Audio Segmentation
      ↓
ASR
      ↓
ATC Semantic Parser
      ↓
Timeline
      ↓
Search / Replay / Analysis
```

Người sử dụng có thể:

* Nghe lại.
* Xem transcript.
* Click transcript để phát audio đúng timestamp.
* Tìm callsign.
* Tìm huấn lệnh.
* Xác định readback.
* Phân tích sự kiện.

---

# 3. Nguyên tắc thiết kế quan trọng

Không nên xây dựng hệ thống dưới dạng một ứng dụng Speech-to-Text thông thường.

Ví dụ ATCO phát:

```text
Vietnam Airlines three seven two,
descend flight level one two zero,
turn left heading two seven zero.
```

Speech Recognition có thể tạo:

```text
Vietnam Airlines 372 descend flight level 120
turn left heading 270
```

Nhưng hệ thống cần hiểu sâu hơn:

```json
{
  "speaker": "ATCO",
  "callsign": "HVN372",
  "commands": [
    {
      "type": "FLIGHT_LEVEL",
      "action": "DESCEND",
      "value": 120
    },
    {
      "type": "HEADING",
      "action": "TURN_LEFT",
      "value": 270
    }
  ]
}
```

Vì vậy hệ thống cần ít nhất hai tầng:

```text
Speech-to-Text
      ↓
ATC Semantic Understanding
```

---

# 4. Kiến trúc tổng thể

```text
                         ┌─────────────────────┐
                         │   ATC LIVE AUDIO    │
                         │ VHF/VCS/Line-in/PTT │
                         └──────────┬──────────┘
                                    │
                                    ▼
┌─────────────────┐       ┌─────────────────────┐
│ RECORDED AUDIO  │──────▶│   AUDIO GATEWAY     │
│ WAV/MP3/FLAC... │       │ normalize/resample  │
└─────────────────┘       │ VAD / segmentation  │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │    ATC ASR ENGINE   │
                          │ Speech → raw text   │
                          └──────────┬──────────┘
                                     │
                    ┌────────────────┼─────────────────┐
                    ▼                ▼                 ▼
             ┌─────────────┐ ┌──────────────┐ ┌──────────────┐
             │ Call-sign   │ │ ATC semantic │ │ Confidence   │
             │ recognizer  │ │ parser       │ │ estimation   │
             └──────┬──────┘ └──────┬───────┘ └──────┬───────┘
                    └───────────────┬┴────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ CLEARANCE ENGINE    │
                         │ heading / FL / RWY  │
                         │ speed / freq / SSR  │
                         └──────────┬──────────┘
                                    │
                           ATCO ↔ PILOT pairing
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ READBACK CHECKER    │
                         │ matched / mismatch  │
                         │ uncertain / missing │
                         └──────────┬──────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               ▼                    ▼                    ▼
       ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
       │ LIVE SCREEN  │     │ SEARCH/REPLAY│     │ AUDIT STORE  │
       │ WebSocket    │     │ timeline     │     │ DB + audio   │
       └──────────────┘     └──────────────┘     └──────────────┘
```

---

# 5. Audio Processing Layer

Audio Gateway chịu trách nhiệm:

* Nhận tín hiệu audio.
* Resampling.
* Normalization.
* Noise suppression nếu phù hợp.
* Voice Activity Detection – VAD.
* PTT detection nếu có dữ liệu tương ứng.
* Chia utterance.
* Timestamp chính xác.
* Streaming audio tới ASR.

Luồng:

```text
Audio Input
   ↓
Decode
   ↓
Resample
   ↓
Normalize
   ↓
VAD/PTT
   ↓
Utterance segmentation
   ↓
ASR streaming
```

Đề xuất chuẩn audio nội bộ:

```text
PCM
16-bit
Mono
16 kHz hoặc sample rate phù hợp với model ASR
```

Không nên phá hủy hoặc ghi đè audio gốc.

---

# 6. Speech Recognition – ASR

ASR cần hỗ trợ hai chế độ.

## Streaming

Dùng cho LIVE mode:

```text
Audio Chunk
    ↓
Partial Transcript
    ↓
Partial Transcript
    ↓
Final Transcript
```

Ví dụ:

```text
HVN372 descend...
```

sau đó:

```text
HVN372 descend flight level...
```

cuối cùng:

```text
HVN372 descend flight level one two zero.
```

## Batch

Dùng cho Recording Mode:

```text
Audio file
   ↓
Segmentation
   ↓
Batch ASR
   ↓
Timestamped transcript
```

---

# 7. Công nghệ ASR có thể khảo sát

Các kiến trúc/model có thể xem xét:

```text
Whisper / Whisper-derived models
Conformer
RNN-T
wav2vec2
XLS-R
NVIDIA NeMo
SpeechBrain
```

Prototype có thể bắt đầu bằng model Whisper-class.

Đối với hệ thống streaming production, nên khảo sát:

```text
Conformer
+
RNN-T
+
Contextual Biasing
+
Domain Language Model
```

---

# 8. ATC Domain Adaptation

Không nên sử dụng nguyên Speech-to-Text phổ thông.

Kiến trúc tốt hơn:

```text
Foundation ASR
      ↓
ATC Fine-tuning
      ↓
ATC Vocabulary
      ↓
Contextual Biasing
      ↓
Language Model Rescoring
      ↓
ATC Semantic Parser
```

Corpus cần bao gồm:

* ATCO speech.
* Pilot speech.
* Callsigns.
* ICAO alphabet.
* Aviation numeric pronunciation.
* Waypoints.
* Airport names.
* SID.
* STAR.
* Runway.
* Frequency.
* Flight level.
* Heading.
* QNH.
* SSR.
* Standard phraseology.
* Accent và điều kiện radio đại diện cho môi trường triển khai.

---

# 9. Callsign Recognition

Callsign nên được xây dựng thành một subsystem riêng.

Ví dụ những cách phát âm:

```text
Vietnam three seven two
Vietnam Airlines three seven two
HVN three seven two
three seven two
```

có thể cần ánh xạ về:

```text
HVN372
```

Kiến trúc:

```text
ASR probability
        +
Active flight list
        +
Sector aircraft
        +
Frequency
        +
Phonetic similarity
        +
Recent conversation context
        ↓
Callsign Resolver
```

Không nên tự động chọn callsign với confidence cao nếu dữ liệu không đủ rõ.

Ví dụ sector có:

```text
HVN372
HVN732
HVN3721
THA372
```

Nếu hệ thống chỉ nghe được:

```text
... three seven two
```

thì cần thể hiện:

```text
CALLSIGN UNCERTAIN
```

thay vì đoán chắc chắn.

---

# 10. Aviation Number Recognition

Đây là thành phần đặc biệt quan trọng.

Ví dụ:

```text
TREE FIVE ZERO
```

không nên chỉ lưu:

```text
350
```

Nên giữ:

```json
{
  "spoken": "TREE FIVE ZERO",
  "digits": "350",
  "semanticValue": 350
}
```

Tương tự:

```text
FLIGHT LEVEL ONE TWO ZERO
```

được xử lý:

```text
spoken:
ONE TWO ZERO

numeric:
120

semantic:
FL120
```

Việc giữ dữ liệu từng lớp rất có giá trị trong:

* Debugging.
* Training.
* Auditing.
* Incident investigation.
* Error analysis.

---

# 11. ATC Semantic Parser

Semantic Parser cần xác định các entity và intent.

Các entity quan trọng:

| Entity       | Ví dụ      |
| ------------ | ---------- |
| Callsign     | HVN372     |
| Flight level | FL120      |
| Altitude     | 5000 FT    |
| Heading      | HDG270     |
| Speed        | 220 KT     |
| Runway       | RWY25L     |
| Frequency    | 120.900    |
| SSR          | 4271       |
| QNH          | 1013       |
| SID          | SID name   |
| STAR         | STAR name  |
| Waypoint     | DAD        |
| Approach     | ILS / RNAV |

Các intent:

```text
CLIMB
DESCEND
MAINTAIN
TURN_LEFT
TURN_RIGHT
CONTACT
SQUAWK
CLEARED_APPROACH
CLEARED_TAKEOFF
CLEARED_LAND
HOLD_SHORT
LINE_UP
REPORT
PROCEED
DIRECT
REDUCE_SPEED
INCREASE_SPEED
```

---

# 12. Cấu trúc dữ liệu semantic

Ví dụ:

```json
{
  "timestamp": "2026-09-17T12:41:32.420Z",
  "speaker": "ATCO",
  "callsign": {
    "spoken": "VIETNAM AIRLINES THREE SEVEN TWO",
    "normalized": "HVN372",
    "confidence": 0.97
  },
  "rawTranscript": "Vietnam Airlines three seven two descend flight level one two zero turn left heading two seven zero",
  "commands": [
    {
      "type": "ALTITUDE",
      "action": "DESCEND",
      "value": 120,
      "unit": "FL",
      "confidence": 0.98
    },
    {
      "type": "HEADING",
      "action": "TURN_LEFT",
      "value": 270,
      "unit": "DEG",
      "confidence": 0.96
    }
  ],
  "status": "AWAITING_READBACK"
}
```

---

# 13. Clearance Engine

Clearance Engine nhận dữ liệu semantic và duy trì trạng thái huấn lệnh.

Ví dụ:

```text
HVN372 DESCEND FL120
```

hệ thống tạo:

```text
Clearance ID: CLR-19382
Aircraft: HVN372
Type: FLIGHT_LEVEL
Action: DESCEND
Value: 120
Status: AWAITING_READBACK
```

Nếu có nhiều lệnh:

```text
HVN372
DESCEND FL120
TURN LEFT HDG270
```

hệ thống lưu hai command thuộc cùng clearance.

---

# 14. Readback Matching

Ví dụ clearance:

```text
HVN372 DESCEND FL120
TURN LEFT HDG270
```

pilot readback:

```text
DESCENDING FL120
LEFT HEADING 270
HVN372
```

hệ thống tạo:

```text
CALLSIGN      HVN372      ✓
FLIGHT LEVEL  FL120       ✓
HEADING       270 LEFT    ✓

READBACK STATUS:
MATCHED
```

Nếu pilot nói:

```text
DESCENDING FL130
```

hệ thống tạo:

```text
CLEARANCE     READBACK

FL120         FL130
```

Trạng thái:

```text
MISMATCH
```

Hệ thống chỉ hỗ trợ nhận biết sai khác, không tự quyết định máy bay phải thực hiện lệnh nào.

---

# 15. Các trạng thái readback

Đề xuất:

```text
AWAITING_READBACK
MATCHED
MISMATCH
PARTIAL
MISSING
UNCERTAIN
SUPERSEDED
CANCELLED
HUMAN_VERIFIED
```

---

# 16. Confidence Model

Không nên chỉ tính confidence cả câu.

Ví dụ:

```text
Sentence confidence = 94%
```

chưa đủ.

Nên tách:

```text
Transcript confidence : 0.94
Callsign confidence   : 0.71
Intent confidence     : 0.98
Flight level          : 0.99
Heading               : 0.96
```

UI có thể hiển thị:

```text
? HVN372
DESCEND FL120
```

nếu callsign chưa chắc chắn.

---

# 17. Contextual ASR

Có thể tăng độ chính xác bằng dữ liệu ATM.

Ví dụ hiện tại sector có:

```text
HVN372
VJC819
THA551
SIA186
```

ASR nên được bias về các callsign trên.

Nếu danh sách waypoint hiện hành là:

```text
DAN
DAGAG
PANDI
BITOD
```

thì các token này được tăng xác suất.

Nếu runway khai thác:

```text
25L
25R
```

ASR có thể ưu tiên hai runway này.

Kiến trúc:

```text
Flight Data
     │
Surveillance
     │
Sector State
     │
Airport Configuration
     │
     ▼
Context Provider
     ↓
ASR Contextual Biasing
     ↓
Speech Recognition
```

---

# 18. Speaker Role Detection

Hệ thống cần phân biệt tối thiểu:

```text
ATCO
PILOT
UNKNOWN
```

Có thể dựa vào:

* Channel metadata.
* PTT metadata.
* Radio routing.
* Voice identification nếu được phép.
* Phraseology.
* Conversation structure.

Nếu không chắc chắn:

```text
speaker = UNKNOWN
```

không nên tự đoán quá mức.

---

# 19. Data Model

Không nên chỉ có một bảng transcript.

Đề xuất:

```text
AudioSession
Utterance
Aircraft
Clearance
Command
Readback
SemanticEntity
AudioSegment
UserCorrection
AuditEvent
```

---

# 20. AudioSession

```text
id
frequency
sector
controllerPosition
startedAt
endedAt
sourceType
audioUri
sampleRate
channel
metadata
```

---

# 21. Utterance

```text
id
sessionId
startedAt
endedAt
speakerRole
rawTranscript
normalizedTranscript
confidence
audioOffsetStart
audioOffsetEnd
processingVersion
```

---

# 22. Clearance

```text
id
utteranceId
aircraftCallsign
createdAt
status
confidence
```

---

# 23. Command

```text
id
clearanceId
type
action
value
unit
confidence
```

---

# 24. Readback

```text
id
clearanceId
utteranceId
status
confidence
discrepancy
```

---

# 25. AuditEvent

```text
id
eventType
userId
timestamp
entityType
entityId
before
after
```

Cần phân biệt:

```text
AI generated
Human corrected
Human verified
```

---

# 26. Raw Transcript và Normalized Transcript

Hai trường phải giữ độc lập.

Ví dụ:

```text
RAW:

viet nam three seven two climb flight level too five zero
```

Normalized:

```text
HVN372 CLIMB FL250
```

Không nên sửa trực tiếp `rawTranscript`.

---

# 27. Live User Interface

Đề xuất bố cục:

```text
┌──────────────────────────────────────────────────────────────┐
│ LIVE • 120.900 • APP                           REC ● 19:41:35 │
├───────────────┬──────────────────────────────────────────────┤
│ AIRCRAFT      │ LIVE COMMUNICATION                           │
│               │                                              │
│ HVN372        │ 19:41:30 ATCO                               │
│ VJC819        │ HVN372 DESCEND FL120                         │
│ THA551        │ FL120                     confidence 98%      │
│ SIA186        │                                              │
│               │ 19:41:34 PILOT                              │
│               │ DESCENDING FL120 HVN372                      │
│               │                  ✓ READBACK MATCHED           │
├───────────────┼──────────────────────────────────────────────┤
│ CLEARANCES    │ WARNINGS                                     │
│ HVN372 FL120  │ —                                            │
│ VJC819 H270   │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

---

# 28. Màu và trạng thái UI

Không nên chỉ dựa trên màu sắc.

Dùng đồng thời icon và text:

```text
✓ MATCHED
! MISMATCH
? UNCERTAIN
… WAITING READBACK
```

Có thể dùng:

```text
Green  + ✓
Amber  + ?
Red    + !
Grey   + …
```

nhưng nội dung text vẫn phải luôn hiện diện.

---

# 29. Recording / Replay UI

Giao diện dạng audio editor:

```text
┌─────────────────────────────────────────────────────────────┐
│ ACC_20260917_1200.wav                           00:21:38     │
├─────────────────────────────────────────────────────────────┤
│ ▂▅▇▃▂▂▅████▃▂▆▇▃▂▂▅▆▇▂▂ waveform                        │
│       ▲                                                     │
│     cursor                                                  │
├─────────────────────────────────────────────────────────────┤
│ 00:21:31 ATCO  HVN372 DESCEND FL120                         │
│ 00:21:34 PILOT HVN372 DESCENDING FL130      ⚠ FL mismatch   │
│ 00:21:39 ATCO  HVN372 NEGATIVE DESCEND FL120                │
├─────────────────────────────────────────────────────────────┤
│ Search: [ HVN372        ] [callsign] [FL] [runway] [time]   │
└─────────────────────────────────────────────────────────────┘
```

Click transcript:

```javascript
audio.currentTime = utterance.audioOffsetStart;
audio.play();
```

---

# 30. Search Engine

Cho phép tìm theo:

```text
Callsign
Time
Frequency
Sector
Flight Level
Altitude
Heading
Runway
SSR
Frequency instruction
Waypoint
ATCO
Pilot
Clearance type
Readback mismatch
Confidence
```

Ví dụ:

```text
callsign = HVN372
AND
time BETWEEN 12:00 AND 13:00
AND
readback_status = MISMATCH
```

---

# 31. Stack công nghệ đề xuất

## Frontend

```text
React
TypeScript
Vite
WebSocket
Web Audio API
Wavesurfer.js
```

Có thể dùng:

```text
Tailwind CSS
Material UI
Radix UI
```

tùy hệ thống design.

---

# 32. Backend

Đề xuất:

```text
Python
FastAPI
Pydantic
SQLAlchemy
```

FastAPI phù hợp với:

* REST.
* WebSocket.
* Python AI stack.
* Async processing.

---

# 33. Database

Dùng:

```text
PostgreSQL
```

cho dữ liệu nghiệp vụ.

Search nâng cao có thể dùng:

```text
PostgreSQL Full Text Search
```

hoặc:

```text
OpenSearch / Elasticsearch
```

---

# 34. Audio Storage

Có thể sử dụng:

```text
MinIO
```

hoặc hệ thống:

```text
S3-compatible object storage
```

Audio nên lưu độc lập với database.

Database chỉ lưu:

```text
audioUri
timestamp
offset
metadata
hash
```

---

# 35. Realtime Communication

Frontend ↔ Backend dùng:

```text
WebSocket
```

Ví dụ:

```text
WS /api/v1/sessions/{sessionId}/stream
```

---

# 36. WebSocket Events

Partial transcript:

```json
{
  "event": "transcript.partial",
  "utteranceId": "utt-982",
  "text": "HVN372 descend flight",
  "confidence": 0.82
}
```

Final transcript:

```json
{
  "event": "transcript.final",
  "utteranceId": "utt-982",
  "text": "HVN372 descend flight level one two zero",
  "confidence": 0.96
}
```

---

# 37. Clearance Event

```json
{
  "event": "clearance.detected",
  "utteranceId": "utt-982",
  "callsign": "HVN372",
  "commands": [
    {
      "type": "FLIGHT_LEVEL",
      "action": "DESCEND",
      "value": 120,
      "confidence": 0.98
    }
  ]
}
```

---

# 38. Readback Event

```json
{
  "event": "readback.checked",
  "callsign": "HVN372",
  "clearanceId": "clr-786",
  "status": "MATCHED"
}
```

Nếu sai:

```json
{
  "event": "readback.checked",
  "callsign": "HVN372",
  "clearanceId": "clr-786",
  "status": "MISMATCH",
  "differences": [
    {
      "field": "flight_level",
      "expected": 120,
      "readback": 130
    }
  ]
}
```

---

# 39. Microservice Architecture

Đề xuất:

```text
Frontend
   │
   ▼
API Gateway
   │
   ├── Authentication Service
   │
   ├── Session Service
   │
   ├── Audio Service
   │
   ├── Transcript Service
   │
   ├── ATC Semantic Service
   │
   ├── Clearance Service
   │
   ├── Readback Service
   │
   ├── Search Service
   │
   └── Audit Service
               │
               ▼
          ASR GPU Server
```

Không nhất thiết phải chia thành microservices ngay từ MVP.

Có thể xây modular monolith trước.

---

# 40. Event Bus

Khi hệ thống lớn hơn có thể sử dụng:

```text
Redis Streams
```

hoặc:

```text
Apache Kafka
```

Ví dụ:

```text
audio.received
audio.segmented
transcript.partial
transcript.final
semantic.completed
clearance.detected
readback.detected
readback.mismatch
human.corrected
```

---

# 41. Deployment

Khuyến nghị đối với dữ liệu ATC thật:

```text
ATC Network
     │
     ▼
Audio Gateway
     │
     ▼
Private LAN
     │
┌────┴────────────────────────────┐
│ On-Premises Processing Cluster │
│                                │
│ API                            │
│ ASR GPU                        │
│ NLP                            │
│ PostgreSQL                     │
│ Object Storage                 │
│ Monitoring                     │
│ Audit                          │
└──────────────┬─────────────────┘
               │
               ▼
ATCO / Supervisor / Investigator
```

Ưu tiên on-premises hoặc môi trường mạng được kiểm soát phù hợp với yêu cầu bảo mật của đơn vị.

Không nên mặc định truyền audio ATC thật đến dịch vụ cloud bên ngoài.

---

# 42. Containerization

Dùng:

```text
Docker
```

Production có thể dùng:

```text
Kubernetes
```

nếu có nhu cầu:

* High availability.
* GPU scheduling.
* Scaling.
* Rolling deployment.
* Service isolation.

---

# 43. Authentication và Authorization

Khuyến nghị:

```text
OIDC / OAuth2
```

Có thể sử dụng:

```text
Keycloak
```

Roles:

```text
ATCO
Supervisor
Instructor
Investigator
Administrator
ML Engineer
Auditor
```

---

# 44. Audit

Các chỉnh sửa thủ công phải lưu:

```text
User
Timestamp
Old value
New value
Reason
Source
```

Ví dụ:

```text
AI:

HVN732
```

người dùng sửa:

```text
HVN372
```

Audit:

```json
{
  "type": "TRANSCRIPT_CORRECTION",
  "before": "HVN732",
  "after": "HVN372",
  "source": "HUMAN"
}
```

Dữ liệu này đồng thời rất hữu ích cho retraining.

---

# 45. Human Verification

Giao diện phải phân biệt rõ:

```text
HEARD AUDIO
       ↓
AI TRANSCRIPT
       ↓
AI INTERPRETATION
       ↓
HUMAN VERIFIED
```

Không được coi:

```text
ASR confidence = 99%
```

là tương đương:

```text
ATCO VERIFIED
```

---

# 46. Monitoring

Sử dụng:

```text
Prometheus
Grafana
```

Log:

```text
Loki
```

hoặc:

```text
ELK
```

Theo dõi:

```text
ASR latency
WebSocket latency
GPU utilization
Audio queue delay
ASR failures
Parser failures
Callsign uncertainty
Mismatch alerts
Database latency
Storage errors
```

---

# 47. Chỉ số đánh giá AI

Không nên chỉ đo WER.

Cần đo:

| Metric                     | Ý nghĩa               |
| -------------------------- | --------------------- |
| WER                        | lỗi từ                |
| Callsign Accuracy          | nhận đúng callsign    |
| Callsign False Association | ghép nhầm aircraft    |
| Numeric Accuracy           | nhận đúng số          |
| Flight Level Accuracy      | nhận đúng FL          |
| Heading Accuracy           | nhận đúng heading     |
| Speed Accuracy             | nhận đúng speed       |
| Frequency Accuracy         | nhận đúng frequency   |
| Runway Accuracy            | nhận đúng runway      |
| Command Accuracy           | nhận đúng loại lệnh   |
| Readback Recall            | bắt được readback     |
| Mismatch Recall            | bắt được readback sai |
| False Alert Rate           | cảnh báo nhầm         |
| End-to-End Latency         | độ trễ tổng           |

---

# 48. Ví dụ đánh giá

Không nên chỉ báo:

```text
WER = 7%
```

vì có thể:

```text
Callsign Accuracy = 91%
Flight Level Accuracy = 92%
```

vẫn chưa đáp ứng mục tiêu của ứng dụng.

Cần ưu tiên entity quan trọng:

```text
Callsign
Flight Level
Altitude
Heading
Runway
Frequency
SSR
```

---

# 49. Dataset

Một utterance nên có annotation:

```json
{
  "audio": "segment_000387.wav",
  "speaker": "ATCO",
  "language": "en",
  "transcript": "Viet Nam three seven two descend flight level one two zero",
  "callsign": "HVN372",
  "intent": "DESCEND",
  "entities": {
    "flight_level": 120
  }
}
```

Readback:

```json
{
  "speaker": "PILOT",
  "callsign": "HVN372",
  "intent": "READBACK",
  "entities": {
    "flight_level": 120
  },
  "linked_clearance": "CLR-19382"
}
```

---

# 50. Dataset Versioning

Nên lưu:

```text
dataset version
annotation version
annotator
reviewer
model version
processing pipeline version
```

Ví dụ:

```text
Dataset v1.4
ASR v2.3
Semantic Parser v1.8
Callsign Resolver v1.2
```

để có thể tái tạo kết quả.

---

# 51. MVP Phase 1 – Offline Transcript

Đầu tiên chỉ cần:

```text
Upload WAV
    ↓
ASR
    ↓
Transcript
    ↓
Timeline
    ↓
Waveform
```

Chức năng:

* Upload file.
* Play/Pause.
* Waveform.
* Transcript.
* Timestamp.
* Edit transcript.
* Search.

---

# 52. MVP Phase 2 – ATC Semantic Parser

Thêm:

```text
Callsign
Flight Level
Heading
Speed
Runway
Frequency
SSR
QNH
Waypoint
```

Ví dụ UI:

```text
HVN372

DESCEND
FL120

TURN LEFT
HDG270
```

---

# 53. MVP Phase 3 – Dataset Collection

Mỗi correction từ người dùng tạo:

```text
Audio
+
Original AI Transcript
+
Corrected Transcript
+
Semantic Labels
```

Tập này trở thành corpus huấn luyện nội bộ.

---

# 54. MVP Phase 4 – Live Streaming

Thêm:

```text
Audio Gateway
WebSocket
Streaming ASR
Partial Transcript
Final Transcript
```

Mục tiêu kỹ thuật prototype có thể đặt:

```text
Partial transcript: khoảng 300–800 ms

Final utterance:
dưới khoảng 2 giây sau khi kết thúc câu

Semantic parsing:
<100 ms

UI update:
<100 ms
```

Đây là mục tiêu thiết kế prototype, không phải tiêu chuẩn khai thác hay chứng nhận.

---

# 55. MVP Phase 5 – Clearance / Readback

Thêm:

```text
Clearance state
Readback state
Pairing
Mismatch detection
Missing readback detection
Confidence
```

Ví dụ:

```text
ATCO:
HVN372 CLIMB FL280 HDG310

PILOT:
HVN372 CLIMB FL280 HDG300
```

Hệ thống hiển thị:

```text
              CLEARANCE     READBACK

Callsign      HVN372        HVN372       ✓
Flight Level  FL280         FL280        ✓
Heading       310           300          ✕
```

---

# 56. MVP Phase 6 – Integration

Sau khi hệ thống ổn định có thể nghiên cứu tích hợp với:

```text
Flight Data Processing
Surveillance data
Sector configuration
Airport/runway configuration
VCS
Recording system
```

Chỉ thực hiện khi kiến trúc và chính sách của hệ thống khai thác cho phép.

---

# 57. Security

Cần xem xét:

```text
Network segmentation
TLS
Encryption at rest
RBAC
Audit
Secure backup
Offline backup
Secret management
Access logging
Time synchronization
```

Nên bảo vệ audio và transcript như dữ liệu nghiệp vụ quan trọng.

---

# 58. High Availability

Nếu triển khai production có thể thiết kế:

```text
2 × API nodes
2 × Database nodes
N × ASR GPU workers
Object storage replication
Message queue replication
Monitoring nodes
```

Audio ingestion không nên phụ thuộc vào một server duy nhất nếu có yêu cầu availability cao.

---

# 59. Time Synchronization

Rất quan trọng với:

```text
Audio
Transcript
Radar
Flight data
Audit
Events
```

Các hệ thống cần cùng time reference phù hợp.

Mỗi utterance nên có:

```text
absolute timestamp
audio offset
session timestamp
```

---

# 60. Error Handling

Nếu ASR không chắc chắn:

```text
UNCERTAIN
```

Nếu semantic parser không hiểu:

```text
UNPARSED
```

Nếu callsign không rõ:

```text
CALLSIGN_UNKNOWN
```

Nếu audio mất:

```text
AUDIO_GAP
```

Không nên tự điền dữ liệu nghiệp vụ dựa trên suy đoán nếu confidence không đủ.

---

# 61. Một nguyên tắc quan trọng cho AI

Hệ thống nên ưu tiên:

```text
UNKNOWN
```

hơn:

```text
WRONG BUT CONFIDENT
```

Ví dụ:

```text
? callsign

DESCEND FL120
```

tốt hơn:

```text
HVN372 DESCEND FL120
```

nếu thực tế máy chưa xác định được callsign.

---

# 62. Các module của sản phẩm hoàn chỉnh

```text
┌─────────────────────────────────────────┐
│             ATC VOICE SYSTEM            │
├─────────────────────────────────────────┤
│                                         │
│ 1. Live Monitor                         │
│    realtime radio → transcript          │
│                                         │
│ 2. Recording Analyzer                   │
│    audio file → timeline → transcript   │
│                                         │
│ 3. Clearance Intelligence               │
│    callsign / FL / HDG / RWY / FREQ     │
│                                         │
│ 4. Readback Analyzer                    │
│    clearance ↔ pilot readback           │
│                                         │
│ 5. Search & Investigation               │
│    audio / callsign / time / command    │
│                                         │
│ 6. Annotation                           │
│    human correction                     │
│                                         │
│ 7. Administration                       │
│    users / models / audit               │
│                                         │
└─────────────────────────────────────────┘
```

---

# 63. Lộ trình phát triển đề xuất

```text
Phase 1
Recorded audio
→ transcript

Phase 2
Transcript
→ ATC semantic entities

Phase 3
Human correction
→ ATC dataset

Phase 4
Streaming audio
→ realtime transcript

Phase 5
Clearance
↔
Readback

Phase 6
Contextual ATM integration

Phase 7
Validation / Human Factors / Security

Phase 8
Controlled operational evaluation
```

---

# 64. Hướng triển khai ưu tiên

Không nên bắt đầu dự án bằng chức năng:

```text
AI WARNING
```

Ngay phiên bản đầu tiên.

Hướng ưu tiên là:

```text
Băng ghi âm
      ↓
Transcript
      ↓
Timestamp
      ↓
Waveform
      ↓
Human Correction
      ↓
Search
```

Sau đó:

```text
Transcript
      ↓
Semantic Parsing
```

sau đó mới:

```text
Live Recognition
```

và cuối cùng:

```text
Clearance ↔ Readback Assistance
```

Cách tiếp cận này vừa tạo sản phẩm sử dụng được sớm, vừa tạo corpus chất lượng để cải thiện ASR.

---

# 65. Kết luận

Ứng dụng đề xuất không đơn thuần là hệ thống chuyển giọng nói thành văn bản.

Kiến trúc thích hợp là:

```text
AUDIO
  ↓
ASR
  ↓
ATC LANGUAGE UNDERSTANDING
  ↓
CALLSIGN RESOLUTION
  ↓
CLEARANCE EXTRACTION
  ↓
READBACK MATCHING
  ↓
HUMAN VERIFICATION
  ↓
SEARCH / REPLAY / AUDIT
```

Ba subsystem cần được coi là trọng tâm:

```text
1. ATC ASR
2. Callsign Resolver
3. Clearance / Readback Engine
```

Nguyên tắc quan trọng nhất:

```text
AI transcript
≠
Operationally verified information
```

và:

```text
AI interpretation
≠
ATCO decision
```

Hệ thống nên được thiết kế như một **Decision Support / Speech Intelligence System**, trong đó ATCO hoặc người dùng nghiệp vụ vẫn là người xác nhận nội dung cuối cùng.

---

# 66. Tên dự án gợi ý

Một số tên kỹ thuật có thể sử dụng:

```text
ATC Voice Intelligence System
ATC Speech Intelligence
ATC Voice Assistant
ATC Communication Analyzer
ATC Speech Recognition & Readback Assistant
ATC Voice Monitoring System
```

Tên viết tắt ví dụ:

```text
AVIS
ATC Voice Intelligence System
```

hoặc:

```text
ASRA
ATC Speech & Readback Assistant
```

---

# 67. Stack tham khảo cuối cùng

```text
Frontend
├── React
├── TypeScript
├── Web Audio API
├── Wavesurfer.js
└── WebSocket

Backend
├── FastAPI
├── Python
├── PostgreSQL
├── Redis/Kafka
└── MinIO

AI
├── Streaming ASR
├── ATC Language Model
├── Callsign Resolver
├── Semantic Parser
└── Readback Matcher

Infrastructure
├── Docker
├── Kubernetes (optional)
├── NVIDIA GPU
├── Prometheus
├── Grafana
└── Loki/ELK

Security
├── OIDC
├── Keycloak
├── RBAC
├── TLS
├── Audit
└── Encryption
```

---

**Tài liệu thiết kế:** ATC Voice Assistant / ATC Speech Intelligence System
**Định dạng:** Markdown
**Mục đích:** Kiến trúc hệ thống, thiết kế MVP, phát triển AI/ASR, giao diện, backend, dữ liệu và lộ trình triển khai.
