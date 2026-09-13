import json
import os
import shutil
import sys
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "tools"))
import serve  # noqa: E402


def test_creator_signature_ok():
    assert serve.CREATOR_SIGNATURE == "created by Lộc đẹp trai"
    assert serve.creator_signature_ok(root)


def test_creator_signature_missing_file_locks(tmp_path):
    folder = Path(tmp_path)
    (folder / "web").mkdir(parents=True, exist_ok=True)
    try:
        assert serve.creator_signature_ok(folder) is False
        (folder / "SIGNATURE.txt").write_text("tampered", encoding="utf-8")
        (folder / "web" / "SIGNATURE.txt").write_text("tampered", encoding="utf-8")
        assert serve.creator_signature_ok(folder) is False
        (folder / "SIGNATURE.txt").write_text(serve.CREATOR_SIGNATURE + "\n", encoding="utf-8")
        (folder / "web" / "SIGNATURE.txt").write_text(serve.CREATOR_SIGNATURE + "\n", encoding="utf-8")
        assert serve.creator_signature_ok(folder) is True
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_source_web_has_db():
    web = serve.resolve_web(root)
    db = web / "data" / "library.sqlite"
    assert web == root / "web"
    assert db.is_file(), db
    assert db.stat().st_size > 1000


def test_sync_keeps_certs():
    src = root / "web"
    dest = root / "tests" / ".tmp-installed-web"
    certs = dest / "certs"
    certs.mkdir(parents=True, exist_ok=True)
    keep = certs / "keep-me.pem"
    keep.write_text("secret-ca", encoding="utf-8")
    serve.sync_installed_web(src, dest)
    assert (dest / "data" / "library.sqlite").is_file()
    assert (dest / "js" / "library-data.js").is_file()
    assert keep.read_text(encoding="utf-8") == "secret-ca"
    shutil.rmtree(dest, ignore_errors=True)


def test_app_info_without_apk():
    info = serve.app_info("1.2.0", None)
    assert info["version"] == "1.2.0"
    assert info["apk"] is False
    assert info["apkUrl"] is None
    assert info["apkBytes"] == 0


def test_resolve_apk_finds_phat_hanh():
    fake_root = root / "tests" / ".tmp-apk-root"
    apk_dir = fake_root / "phat-hanh"
    apk_dir.mkdir(parents=True, exist_ok=True)
    apk = apk_dir / "ATC-Desk.apk"
    apk.write_bytes(b"PK" + b"\x00" * 2000)
    try:
        found = serve.resolve_apk(fake_root)
        assert found == apk
    finally:
        shutil.rmtree(fake_root, ignore_errors=True)
    assert serve.resolve_apk(fake_root) is None


def _http_get(port: int, path: str):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    res = conn.getresponse()
    body = res.read()
    conn.close()
    return res.status, res.getheader("Content-Type"), body


def test_http_app_info_and_apk():
    fake = root / "tests" / ".tmp-served.apk"
    fake.write_bytes(b"APK-FAKE" + b"\x00" * 2048)
    prev_apk = serve.APK_PATH
    prev_ver = serve.APP_VERSION
    serve.APK_PATH = fake
    serve.APP_VERSION = "1.2.0-test"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.DeskHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        status, ctype, body = _http_get(port, "/app-info.json")
        assert status == 200, (status, body)
        assert "json" in (ctype or "")
        info = json.loads(body)
        assert info["apk"] is True
        assert info["apkUrl"] == "/ATC-Desk.apk"
        assert info["apkBytes"] == fake.stat().st_size

        status, ctype, body = _http_get(port, "/ATC-Desk.apk")
        assert status == 200, status
        assert body.startswith(b"APK-FAKE")
        assert "android.package" in (ctype or "")

        serve.APK_PATH = None
        status, _, _ = _http_get(port, "/ATC-Desk.apk")
        assert status == 404
    finally:
        httpd.shutdown()
        serve.APK_PATH = prev_apk
        serve.APP_VERSION = prev_ver
        fake.unlink(missing_ok=True)


if __name__ == "__main__":
    os.chdir(root)
    test_creator_signature_ok()
    test_creator_signature_missing_file_locks(root / "tests" / ".tmp-sig-root")
    test_source_web_has_db()
    test_sync_keeps_certs()
    test_app_info_without_apk()
    test_resolve_apk_finds_phat_hanh()
    test_http_app_info_and_apk()
    print("serve_paths_test.py: source web + cert-preserving sync + apk routes passed")
