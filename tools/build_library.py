"""Build offline SQLite and browser snapshot from local sources. No downloads."""
import csv
import hashlib
import json
import sqlite3
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'web/data'

def normalize(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', s.lower().replace('đ', 'd')) if unicodedata.category(c) != 'Mn').split())

def build():
    script = "['glossary','lexicon','dict-en-vi'].forEach(f=>require('./web/js/'+f+'.js'));process.stdout.write(JSON.stringify(ATC));"
    old = json.loads(subprocess.check_output(['node', '-e', script], cwd=ROOT).decode('utf-8'))
    sources = [
        dict(id='vn19', title='Thông tư 19/2017/TT-BGTVT, Điều 3', url='https://vbpl.vn/bonoivu/Pages/vbpq-toanvan.aspx?ItemID=122388', note='Đối chiếu 2026-09-11. Văn bản hết hiệu lực một phần; chỉ tham chiếu thuật ngữ, không kết luận quy định hiện hành.'),
        dict(id='pbn', title='ICAO Doc 9613 — PBN Manual', url='https://applications.icao.int/tools/ATMiKIT/story_content/external_files/story_content/external_files/pbn_manual-doc_9613.pdf', note='Tham chiếu khái niệm; bản dịch tiếng Việt biên soạn.'),
        dict(id='editorial', title='ATC Desk — biên soạn', url='', note='Bản dịch gợi ý cho hội nghị; chưa thẩm định chuyên gia độc lập.'),
        dict(id='vatm', title='VATM ATC/ATM Terminology Database', url='', note='Bộ từ vựng VATM, đối chiếu ICAO (Annex / Doc). Xuất từ data/VATM_ATC_ATM_Terminology_Database.xlsx, 2026-09-12. Không thay AIP Việt Nam khi có xung đột.'),
        dict(id='doc4444', title='ICAO Doc 4444 — PANS-ATM, Chapter 12 Phraseologies', url='https://store.icao.int/', note='Huấn lệnh / phraseology vô tuyến chuẩn ICAO (kèm từ chuẩn Annex 10 Vol II). Bản rút gọn song ngữ cho tra cứu điều hành; không phải toàn văn Doc 4444. Bản dịch tiếng Việt theo cách dùng VATM (đường CHC, vào đường CHC và chờ, đặt mã đáp, vòng lại). Đối chiếu Amendment 10 (2021) cho tình trạng bề mặt đường CHC / RCR. Không thay AIP Việt Nam khi có xung đột.'),
        dict(id='aipvn', title='AIP Việt Nam — AD 2.8 đường lăn', url='https://aim.vatm.vn/', note='Ký hiệu đường lăn 22 cảng ACV (+ Vân Đồn). Trích AD 2.8 AIRAC 02/26 (hiệu lực 2026-05-14). Không thay AIP/NOTAM khi có xung đột.'),
        dict(id='icao8585', title='ICAO telephony / callsign hãng bay', url='', note='Callsign vô tuyến các hãng thường xuyên hoặc theo mùa tại Việt Nam. Đối chiếu Doc 8585 và AIP GEN 2.4.'),
        dict(id='editor', title='Editor — nhập tay trên máy này', url='', note='Mẫu huấn lệnh do người dùng thêm. Chưa thẩm định độc lập.'),
        dict(id='legacy', title='Thư viện ATC Desk có sẵn', url='', note='glossary.js / lexicon.js; chưa đối chiếu nguồn từng mục.'),
        dict(id='general', title='Từ điển phổ thông có sẵn — anhviet109K', url='https://github.com/yenthanh132/avdict-database-sqlite-converter', note='Nghĩa đầu rút gọn, có thể thiếu hoặc sai ngữ cảnh; xem NOTICE.txt.')]
    entries = {}
    def add(en, vi, domain, source, abbr='', note=''):
        en, vi = en.strip(), vi.strip()
        if not en or not vi: return
        key = (normalize(en), normalize(vi), domain)
        entries[key] = dict(id=hashlib.sha256('\t'.join(key).encode()).hexdigest()[:20], en=en, vi=vi, domain=domain, source=source, abbr=abbr, note=note, kind='sentence' if en.endswith(('.', '?', '!')) else 'term', status='referenced' if source in ('vn19', 'pbn', 'vatm', 'doc4444', 'aipvn', 'icao8585') else 'unreviewed')
    for en, vi in old['EN_VI_DICT'].items(): add(en, vi, 'general', 'general')
    for r in old['TERMS'] + old['PHRASES']: add(r.get('en',''), r.get('vi',''), 'legacy', 'legacy', r.get('abbr',''))
    for en, vi in old['EN_VI_LEXICON']: add(en, vi, 'legacy', 'legacy')
    with (ROOT / 'data/conference-library.tsv').open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f, delimiter='\t'): add(**row)
    vatm_tsv = ROOT / 'data/vatm-terminology.tsv'
    if vatm_tsv.exists():
        with vatm_tsv.open(encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f, delimiter='\t'): add(**row)
    phrase_tsv = ROOT / 'data/doc4444-phraseology.tsv'
    if phrase_tsv.exists():
        with phrase_tsv.open(encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f, delimiter='\t'): add(**row)
    for extra in ('data/vn-taxiways.tsv', 'data/vn-callsigns.tsv', 'data/user-phraseology.tsv'):
        path = ROOT / extra
        if path.exists():
            with path.open(encoding='utf-8', newline='') as f:
                for row in csv.DictReader(f, delimiter='\t'): add(**row)
    rows = sorted(entries.values(), key=lambda r: (r['domain'], r['en'], r['id']))
    payload = dict(version='2026.09.12.3', sources=sources, entries=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    temp = OUT / 'library.build.sqlite'
    if temp.exists(): temp.unlink()
    with sqlite3.connect(temp) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript('''CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources(id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, note TEXT NOT NULL);
        CREATE TABLE entries(id TEXT PRIMARY KEY, en TEXT NOT NULL, vi TEXT NOT NULL, domain TEXT NOT NULL,
        source TEXT NOT NULL REFERENCES sources(id), abbr TEXT NOT NULL, note TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL);
        CREATE INDEX entries_domain ON entries(domain);
        CREATE INDEX entries_en ON entries(en COLLATE NOCASE);
        CREATE VIRTUAL TABLE entries_fts USING fts5(id UNINDEXED,en,vi,abbr,note, tokenize='unicode61 remove_diacritics 2');''')
        db.execute('INSERT INTO metadata VALUES (?,?)', ('version', payload['version']))
        db.executemany('INSERT INTO sources VALUES (:id,:title,:url,:note)', sources)
        db.executemany('INSERT INTO entries VALUES (:id,:en,:vi,:domain,:source,:abbr,:note,:kind,:status)', rows)
        db.executemany('INSERT INTO entries_fts VALUES (?,?,?,?,?)', [(r['id'], normalize(r['en']), normalize(r['vi']), normalize(r['abbr']), normalize(r['note'])) for r in rows])
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    db.close()
    temp.replace(OUT / 'library.sqlite')
    packed = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    (OUT / 'library.json').write_text(packed, encoding='utf-8')
    (ROOT / 'web/js/library-data.js').write_text('globalThis.ATC_LIBRARY=' + packed + ';\n', encoding='utf-8')
    print(json.dumps({'entries':len(rows), 'domains':{d:sum(r['domain']==d for r in rows) for d in sorted({r['domain'] for r in rows})}}))

if __name__ == '__main__': build()
