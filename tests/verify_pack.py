"""Smoke-test a running ATC Desk server (source or packaged EXE)."""
from __future__ import annotations

import json
import sqlite3
import ssl
import sys
import tempfile
import urllib.request
from pathlib import Path


def get(url: str, n: int | None = None, context=None):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        data = response.read() if n is None else response.read(n)
        length = int(response.headers.get("Content-Length") or len(data))
        return response.status, response.headers.get("Content-Type"), data, length


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18765"
    https = sys.argv[2] if len(sys.argv) > 2 else "https://127.0.0.1:18766"
    ctx = ssl._create_unverified_context()
    checks: list[tuple[bool, str, object]] = []

    pages = [
        ("/", b"ATC Symposium Desk"),
        ("/index.html", "Hội trường".encode("utf-8")),
        ("/glossary.html", "Thuật ngữ".encode("utf-8")),
        ("/briefs.html", "Lập trường".encode("utf-8")),
        ("/cai-dat.html", b"apkCard"),
        ("/js/library-data.js", b"ATC_LIBRARY"),
        ("/css/app.css", b"--accent"),
        ("/js/app.js", b"ATC"),
        ("/manifest.json", b"ATC Desk"),
    ]
    for path, needle in pages:
        status, _ctype, data, size = get(base + path)
        ok = status == 200 and needle in data
        checks.append((ok, path, {"status": status, "size": size, "needle": ok}))

    status, _ctype, blob, size = get(base + "/data/library.sqlite")
    ok = status == 200 and blob.startswith(b"SQLite format 3")
    tmp = Path(tempfile.gettempdir()) / "atc-desk-verify.sqlite"
    tmp.write_bytes(blob)
    db = sqlite3.connect(tmp.as_uri() + "?mode=ro", uri=True)
    n = db.execute("select count(*) from entries").fetchone()[0]
    fts = db.execute("select count(*) from sqlite_master where name='entries_fts'").fetchone()[0]
    db.close()
    checks.append((ok and n > 10000 and fts == 1, "library.sqlite", {"bytes": size, "entries": n, "fts": fts}))

    status, _ctype, data, _size = get(base + "/app-info.json")
    info = json.loads(data)
    checks.append((status == 200 and info.get("apk") is True, "/app-info.json", info))

    status, ctype, data, size = get(base + "/ATC-Desk.apk", n=8)
    checks.append((status == 200 and data.startswith(b"PK"), "/ATC-Desk.apk", {"status": status, "ctype": ctype, "size": size}))

    status, _ctype, data, size = get(https + "/", context=ctx)
    checks.append((status == 200 and b"ATC Symposium Desk" in data, "https /", {"status": status, "size": size}))

    failed = 0
    for ok, name, extra in checks:
        print(("OK  " if ok else "FAIL"), name, extra)
        if not ok:
            failed += 1
    print("FAILS", failed)
    raise SystemExit(failed)


if __name__ == "__main__":
    main()
