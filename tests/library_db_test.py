import json
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root/'web/data/library.json').read_text(encoding='utf-8'))
db = sqlite3.connect((root/'web/data/library.sqlite').as_uri()+'?mode=ro', uri=True)
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert not db.execute('PRAGMA foreign_key_check').fetchall()
assert db.execute('SELECT count(*) FROM entries').fetchone()[0] == len(data['entries'])
assert db.execute('SELECT count(*) FROM entries_fts').fetchone()[0] == len(data['entries'])
assert db.execute("SELECT count(*) FROM entries_fts WHERE entries_fts MATCH ?", ('"dan duong"',)).fetchone()[0] > 10
assert db.execute("SELECT vi FROM entries WHERE abbr='PBN' AND source='vn19'").fetchone()[0] == 'dẫn đường theo tính năng'
assert db.execute("SELECT count(*) FROM entries WHERE source='vatm'").fetchone()[0] >= 300
assert db.execute("SELECT vi FROM entries WHERE abbr='ATCS' AND source='vatm'").fetchone()[0] == 'Dịch vụ kiểm soát không lưu'
assert db.execute("SELECT count(*) FROM entries WHERE source='doc4444'").fetchone()[0] >= 400
assert db.execute("SELECT count(*) FROM entries WHERE domain='phraseology' AND source='doc4444'").fetchone()[0] >= 400
assert db.execute("SELECT vi FROM entries WHERE en='CLEARED TO LAND' AND source='doc4444'").fetchone()[0] == 'Được phép hạ cánh'
assert db.execute("SELECT vi FROM entries WHERE en='LINE UP AND WAIT' AND source='doc4444'").fetchone()[0] == 'Vào đường CHC và chờ'
assert db.execute("SELECT vi FROM entries WHERE en='GO AROUND' AND source='doc4444'").fetchone()[0] == 'Vòng lại'
assert db.execute("SELECT count(*) FROM entries_fts WHERE entries_fts MATCH ?", ('"vao duong chc"',)).fetchone()[0] > 0
assert db.execute("SELECT count(*) FROM entries_fts WHERE entries_fts MATCH ?", ('"duoc phep ha canh"',)).fetchone()[0] > 0
assert db.execute("SELECT count(*) FROM entries WHERE domain='callsign' AND source='icao8585'").fetchone()[0] >= 80
assert db.execute("SELECT count(*) FROM entries WHERE en='VIETJETAIR' AND source='icao8585'").fetchone()[0] == 1
assert db.execute("SELECT count(*) FROM entries WHERE domain='taxiway' AND source='aipvn'").fetchone()[0] >= 150
assert db.execute("SELECT count(*) FROM entries WHERE abbr='VVTS' AND domain='taxiway'").fetchone()[0] == 1
assert db.execute("SELECT count(*) FROM entries WHERE en='TWY S1 (VVTS)'").fetchone()[0] == 1
db.row_factory = sqlite3.Row
stored = {r['id']:dict(r) for r in db.execute('SELECT * FROM entries')}
assert all(stored[r['id']] == r for r in data['entries'])
db.close()
print('library_db_test.py: integrity, FTS, provenance, full JSON parity passed')
