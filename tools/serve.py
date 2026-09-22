"""Serve ATC Symposium Desk over HTTP and HTTPS so phones can install the PWA offline.

Phones need HTTPS (a secure context) for the service worker. This script:
  - HTTP  8765  for the PC and for downloading the local CA
  - HTTPS 8766  for iPhone Safari / Android Chrome (Add to Home Screen)

The CA is generated on this machine (web/certs/). Install it once on the phone.

Frozen one-file EXE (PyInstaller) copies bundled web + DB into
%LOCALAPPDATA%\\ATC-Symposium-Desk so a new Windows PC only needs that EXE.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
import app_paths  # noqa: E402
import media_transcode  # noqa: E402
import media_transcribe  # noqa: E402
from reda.engine import analyze as reda_analyze  # noqa: E402
from reda import store as reda_store  # noqa: E402
from asr_dataset import ingest_finetune  # noqa: E402
from asr_dataset import prepare_mix  # noqa: E402
from asr_eval import eval_payload  # noqa: E402

APP_FOLDER = "ATC-Symposium-Desk"
HTTP_PORT = 8765
HTTPS_PORT = 8766
CREATOR_SIGNATURE = "created by Lộc đẹp trai"
CREATOR_SIGNATURE_SHA256 = "a2fbda0ad4297deda52d14d5dca9af8027c601730cec3ca359982dd151896373"


def _multipart_boundary(content_type: str) -> bytes:
    lower = content_type.lower()
    marker = "boundary="
    idx = lower.find(marker)
    if idx < 0:
        return b""
    raw = content_type[idx + len(marker) :].split(";")[0].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return raw.encode("ascii", "replace")


def _header_attr(header: str, key: str) -> str:
    token = key.lower() + "="
    lower = header.lower()
    idx = lower.find(token)
    if idx < 0:
        return ""
    rest = header[idx + len(token) :].strip()
    if rest.lower().startswith("utf-8''"):
        return unquote(rest.split(";", 1)[0][7:])
    if rest.startswith('"'):
        end = rest.find('"', 1)
        return rest[1:end] if end > 0 else rest.strip('"')
    return rest.split(";")[0].strip()


def parse_multipart_uploads(body: bytes, content_type: str) -> dict[str, tuple[str, bytes]]:
    boundary = _multipart_boundary(content_type)
    if not boundary:
        raise ValueError("Form không phải multipart/form-data.")
    delim = b"--" + boundary
    out: dict[str, tuple[str, bytes]] = {}
    for raw in body.split(delim):
        part = raw
        if part.startswith(b"--"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if not part:
            continue
        header_blob, sep, data = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_blob.decode("utf-8", "replace")
        disp = ""
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disp = line
                break
        name = _header_attr(disp, "name")
        filename = _header_attr(disp, "filename*") or _header_attr(disp, "filename")
        if name:
            out[name] = (Path(filename).name if filename else "", data)
    return out


LOCKED_HTML = (
    "<!doctype html><html lang='vi'><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "<title>Ứng dụng đã khóa</title><body style='margin:0;min-height:100vh;"
    "display:grid;place-items:center;background:#061018;color:#e7eef6;"
    "font-family:Segoe UI,sans-serif'><main style='text-align:center;max-width:28rem;padding:24px'>"
    "<p style='letter-spacing:.2em;color:#e2b15a;text-transform:uppercase;font-size:12px'>Locked</p>"
    "<h1 style='font-size:1.4rem'>Ứng dụng đã bị khóa</h1>"
    "<p style='color:#8aa0b5'>Chữ ký số bị thay đổi hoặc thiếu file SIGNATURE.txt. "
    "Khôi phục đúng nội dung <b>created by Lộc đẹp trai</b> rồi mở lại ứng dụng.</p>"
    "</main></body></html>"
).encode("utf-8")


def _startup_contains_signature() -> bool:
    try:
        return CREATOR_SIGNATURE in Path(__file__).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return bool(getattr(sys, "frozen", False))


def creator_hash_ok() -> bool:
    digest = hashlib.sha256(CREATOR_SIGNATURE.encode("utf-8")).hexdigest()
    return digest == CREATOR_SIGNATURE_SHA256 and _startup_contains_signature()


def _signature_text(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def install_signature(src_root: Path, dest_root: Path) -> None:
    """Copy SIGNATURE.txt on first install only. Do not restore after deletion."""
    src = src_root / "SIGNATURE.txt"
    dest = dest_root / "SIGNATURE.txt"
    marker = dest_root / "installed-version.txt"
    if marker.is_file() and not dest.is_file():
        return
    if dest.is_file() or not src.is_file():
        return
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def signature_files(root: Path | None = None) -> list[Path]:
    if frozen():
        files = [app_home() / "SIGNATURE.txt"]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            files.append(Path(meipass) / "SIGNATURE.txt")
        return files
    base = root if root is not None else bundle_root()
    return [base / "SIGNATURE.txt", base / "web" / "SIGNATURE.txt"]


def creator_signature_ok(root: Path | None = None) -> bool:
    if not creator_hash_ok():
        return False
    files = signature_files(root)
    if not files:
        return False
    for path in files:
        if _signature_text(path) != CREATOR_SIGNATURE:
            return False
    return True


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW("ATC Symposium Desk")
        except (AttributeError, OSError):
            pass


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def app_home() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / APP_FOLDER


def read_version(root: Path) -> str:
    path = root / "VERSION"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def sync_installed_web(src: Path, dest: Path) -> None:
    """Copy bundled UI + DB into a writable folder; keep existing HTTPS certs."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name == "certs":
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    (dest / "certs").mkdir(parents=True, exist_ok=True)


def resolve_web(bundle: Path | None = None) -> Path:
    """Source checkout serves repo web/. Frozen EXE installs a copy under AppData."""
    root = bundle if bundle is not None else bundle_root()
    src = root / "web"
    if not frozen():
        return src
    dest_root = app_home()
    dest = dest_root / "web"
    marker = dest_root / "installed-version.txt"
    install_signature(root, dest_root)
    version = read_version(root)
    installed = ""
    try:
        installed = marker.read_text(encoding="utf-8").strip()
    except OSError:
        installed = ""
    db = dest / "data" / "library.sqlite"
    if installed != version or not db.is_file():
        sync_installed_web(src, dest)
        dest_root.mkdir(parents=True, exist_ok=True)
        marker.write_text(version + "\n", encoding="utf-8")
    return dest


ROOT = bundle_root()
WEB = ROOT / "web"
CERTS = WEB / "certs"
APK_PATH: Path | None = None
APP_VERSION = ""
USER_LIBRARY_MAX = 2000


def user_library_path() -> Path:
    if frozen():
        path = app_home() / "data" / "user-phraseology.json"
    else:
        path = bundle_root() / "data" / "user-phraseology.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_user_library() -> list[dict]:
    path = user_library_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("en") and r.get("vi")][:USER_LIBRARY_MAX]


def save_user_library(rows: list[dict]) -> None:
    cleaned = []
    for raw in rows[:USER_LIBRARY_MAX]:
        if not isinstance(raw, dict):
            continue
        en = str(raw.get("en") or "").strip()[:240]
        vi = str(raw.get("vi") or "").strip()[:240]
        if not en or not vi:
            continue
        cleaned.append(
            {
                "id": str(raw.get("id") or "")[:40],
                "abbr": str(raw.get("abbr") or "").strip()[:24],
                "en": en,
                "vi": vi,
                "note": str(raw.get("note") or "").strip()[:500],
                "domain": "editor",
                "source": "editor",
                "kind": "sentence" if str(raw.get("kind") or "") == "sentence" or en.endswith((".", "?", "!")) else "term",
                "status": "unreviewed",
            }
        )
    user_library_path().write_text(
        json.dumps({"entries": cleaned}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_apk(bundle: Path | None = None) -> Path | None:
    """APK next to the EXE, extracted bundle, AppData, or repo phat-hanh/."""
    root = bundle if bundle is not None else bundle_root()
    candidates: list[Path] = []
    names = ("ATC-Desk-Mobile.apk", "ATC-Desk.apk")
    if frozen():
        parent = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, "_MEIPASS"))
        home = app_home()
        for name in names:
            candidates.extend([parent / name, meipass / name, home / name])
    for name in names:
        candidates.append(root / "phat-hanh" / name)
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            if path.is_file() and path.stat().st_size > 1000:
                return path
        except OSError:
            continue
    return None


def app_info(version: str, apk: Path | None) -> dict:
    payload = {
        "name": "ATC Symposium Desk",
        "version": version,
        "apk": apk is not None,
        "apkUrl": "/ATC-Desk-Mobile.apk" if apk is not None else None,
        "apkBytes": 0,
    }
    if apk is not None:
        try:
            payload["apkBytes"] = apk.stat().st_size
        except OSError:
            payload["apk"] = False
            payload["apkUrl"] = None
    return payload


def lan_ipv4s() -> list[str]:
    found: list[str] = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.4)
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            found.append(ip)
    except OSError:
        pass
    return found


def _need_cryptography() -> None:
    try:
        import cryptography  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Can HTTPS: pip install cryptography\n" + str(exc)
        ) from exc


def ensure_certs(ips: list[str]) -> tuple[Path, Path, Path]:
    _need_cryptography()
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    CERTS.mkdir(parents=True, exist_ok=True)
    ca_key_path = CERTS / "ca-key.pem"
    ca_pem_path = CERTS / "ca.pem"
    ca_cer_path = CERTS / "ATC-Desk-CA.cer"
    leaf_key_path = CERTS / "server-key.pem"
    leaf_pem_path = CERTS / "server.pem"
    meta_path = CERTS / "meta.json"

    names = ["localhost", "127.0.0.1", "::1"] + ips
    meta = {"sans": names}

    def write_ca(key: rsa.RSAPrivateKey) -> x509.Certificate:
        now = datetime.now(timezone.utc)
        name = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ATC Symposium Desk"),
                x509.NameAttribute(NameOID.COMMON_NAME, "ATC Symposium Desk Local CA"),
            ]
        )
        ca = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )
        ca_pem_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        ca_cer_path.write_bytes(ca.public_bytes(serialization.Encoding.DER))
        return ca

    if ca_key_path.exists() and ca_pem_path.exists():
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        ca_cert = x509.load_pem_x509_certificate(ca_pem_path.read_bytes())
        if not ca_cer_path.exists():
            ca_cer_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.DER))
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_key_path.write_bytes(
            ca_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        ca_cert = write_ca(ca_key)

    reuse = False
    if meta_path.exists() and leaf_pem_path.exists() and leaf_key_path.exists():
        try:
            prev = json.loads(meta_path.read_text(encoding="utf-8"))
            reuse = prev.get("sans") == names
        except (OSError, json.JSONDecodeError, TypeError):
            reuse = False

    if not reuse:
        leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        san: list[x509.GeneralName] = []
        for raw in names:
            try:
                san.append(x509.IPAddress(ipaddress.ip_address(raw)))
            except ValueError:
                san.append(x509.DNSName(raw))
        cn = ips[0] if ips else "localhost"
        leaf = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name(
                    [
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ATC Symposium Desk"),
                        x509.NameAttribute(NameOID.COMMON_NAME, cn),
                    ]
                )
            )
            .issuer_name(ca_cert.subject)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(ca_key, hashes.SHA256())
        )
        leaf_key_path.write_bytes(
            leaf_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        leaf_pem_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return leaf_pem_path, leaf_key_path, ca_cer_path


class DeskHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(WEB), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Created-By", "Loc dep trai")
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if path.lower().endswith(".cer"):
            return "application/x-x509-ca-cert"
        if path.lower().endswith(".pem"):
            return "application/x-pem-file"
        if path.lower().endswith(".apk"):
            return "application/vnd.android.package-archive"
        return super().guess_type(path)

    def _route_path(self) -> str:
        return self.path.split("?", 1)[0]

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_apk(self) -> None:
        apk = APK_PATH
        if apk is None or not apk.is_file():
            self.send_error(404, "ATC-Desk-Mobile.apk khong kem theo ban nay")
            return
        try:
            size = apk.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", 'attachment; filename="ATC-Desk-Mobile.apk"')
            self.end_headers()
            if self.command == "HEAD":
                return
            with apk.open("rb") as fh:
                shutil.copyfileobj(fh, self.wfile, length=256 * 1024)
        except OSError as exc:
            self.send_error(500, str(exc))

    def _send_locked(self) -> None:
        self.send_response(423)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(LOCKED_HTML)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(LOCKED_HTML)

    def do_GET(self) -> None:
        if not creator_signature_ok(ROOT):
            self._send_locked()
            return
        path = self._route_path()
        if path == "/app-info.json":
            self._send_json(app_info(APP_VERSION, APK_PATH))
            return
        if path == "/api/media/transcode/status":
            self._transcode_status()
            return
        if path == "/api/media/transcode/result":
            self._transcode_result()
            return
        if path == "/api/media/transcribe/status":
            self._transcribe_status()
            return
        if path == "/api/library/user":
            self._library_user_get()
            return
        if path == "/api/reda/search":
            self._reda_search()
            return
        if path == "/api/finetune/status":
            self._finetune_status()
            return
        if path == "/api/finetune/job":
            self._finetune_job()
            return
        if path == "/api/finetune/eval":
            self._finetune_eval()
            return
        if path == "/api/finetune/template.xlsx":
            self._finetune_template()
            return
        if path == "/api/finetune/gold":
            self._finetune_gold()
            return
        if path == "/api/finetune/seed-glossary":
            self._finetune_seed_glossary()
            return
        if path in (
            "/ATC-Desk.apk",
            "/ATC-Desk-Mobile.apk",
            "/downloads/ATC-Desk.apk",
            "/downloads/ATC-Desk-Mobile.apk",
        ):
            self._send_apk()
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if not creator_signature_ok(ROOT):
            self._send_locked()
            return
        path = self._route_path()
        if path == "/app-info.json":
            self._send_json(app_info(APP_VERSION, APK_PATH))
            return
        if path in (
            "/ATC-Desk.apk",
            "/ATC-Desk-Mobile.apk",
            "/downloads/ATC-Desk.apk",
            "/downloads/ATC-Desk-Mobile.apk",
        ):
            self._send_apk()
            return
        super().do_HEAD()

    def do_POST(self) -> None:
        if not creator_signature_ok(ROOT):
            self._send_locked()
            return
        if self._route_path() == "/api/media/transcode":
            self._transcode_upload()
            return
        if self._route_path() == "/api/media/transcribe":
            self._transcribe_upload()
            return
        if self._route_path() == "/api/reda/analyze":
            self._reda_analyze()
            return
        if self._route_path() == "/api/reda/correction":
            self._reda_correction()
            return
        if self._route_path() == "/api/library/user":
            self._library_user_save()
            return
        if self._route_path() == "/api/finetune/ingest":
            self._finetune_ingest()
            return
        if self._route_path() == "/api/finetune/parse":
            self._finetune_parse()
            return
        if self._route_path() == "/api/finetune/seed-glossary":
            self._finetune_seed_glossary()
            return
        if self._route_path() == "/api/finetune/prepare-mix":
            self._finetune_prepare_mix()
            return
        self.send_error(404, "Not Found")

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("JSON không hợp lệ")
        if not isinstance(payload, dict):
            raise ValueError("JSON phải là object")
        return payload

    def _reda_analyze(self) -> None:
        try:
            body = self._read_json_body()
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, 400)
            return
        turns = body.get("turns") or []
        if not isinstance(turns, list):
            turns = []
        text = str(body.get("text") or "")
        filename = str(body.get("filename") or "")
        try:
            result = reda_analyze(turns=turns, filename=filename, text=text)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        audio_path = str(body.get("audio_path") or "")
        if audio_path:
            result["audio_path"] = audio_path
        try:
            reda_store.save_analysis(result)
        except Exception:
            pass
        self._send_json(result)

    def _reda_search(self) -> None:
        qs = parse_qs(urlparse(self.path).query)
        def one(key: str) -> str:
            vals = qs.get(key) or []
            return str(vals[0]) if vals else ""
        try:
            rows = reda_store.search(
                query=one("q"),
                callsign=one("callsign"),
                status=one("status"),
                speaker=one("speaker"),
            )
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        self._send_json({"ok": True, "hits": rows})

    def _reda_correction(self) -> None:
        try:
            body = self._read_json_body()
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, 400)
            return
        try:
            cid = reda_store.save_correction(
                str(body.get("session_id") or ""),
                str(body.get("utterance_id") or ""),
                str(body.get("before") or ""),
                str(body.get("after") or ""),
                str(body.get("reason") or ""),
            )
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        self._send_json({"ok": True, "id": cid, "source": "HUMAN"})

    def _transcribe_status(self) -> None:
        media_transcribe.sweep_jobs()
        job = media_transcribe.job_snapshot(self._query_id())
        if not job:
            self._send_json({"ok": False, "error": "Khong tim thay tien trinh ghi loi."}, 404)
            return
        job["ok"] = True
        self._send_json(job)

    def _transcribe_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json({"ok": False, "error": "Thieu du lieu file."}, 400)
            return
        if length > media_transcribe.MAX_UPLOAD_BYTES:
            self._send_json({"ok": False, "error": "File qua lon (toi da 512 MB)."}, 413)
            return
        suffix = Path(self._upload_name()).suffix or ".mp4"
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        src = Path(handle.name)
        started = False
        try:
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                handle.write(chunk)
                remaining -= len(chunk)
            handle.close()
            job_id = media_transcribe.start_job(src, self._upload_name())
            started = True
            self._send_json({"ok": True, "id": job_id})
        except OSError as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
        finally:
            try:
                handle.close()
            except Exception:
                pass
            if not started:
                try:
                    src.unlink(missing_ok=True)
                except OSError:
                    pass

    def _finetune_status(self) -> None:
        self._send_json(ingest_finetune.corpus_stats())

    def _finetune_job(self) -> None:
        job_id = self._query_id()
        job = ingest_finetune.job_snapshot(job_id) or prepare_mix.job_snapshot(job_id)
        if not job:
            self._send_json({"ok": False, "error": "Khong tim thay tien trinh fine-tune."}, 404)
            return
        job["ok"] = True
        self._send_json(job)

    def _finetune_eval(self) -> None:
        qs = parse_qs(urlparse(self.path).query)
        mix = (qs.get("mix") or [""])[0].strip() in {"1", "true", "yes"}
        try:
            payload = eval_payload(from_corrections=not mix, mix=mix)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        self._send_json(payload)

    def _finetune_prepare_mix(self) -> None:
        try:
            job_id = prepare_mix.start_prepare()
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        self._send_json({"ok": True, "id": job_id})

    def _finetune_template(self) -> None:
        dest = Path(tempfile.gettempdir()) / "ATC-Desk-finetune-template.xlsx"
        ingest_finetune.write_template(dest)
        data = dest.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", 'attachment; filename="ATC-Desk-VHF-finetune.xlsx"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _finetune_ingest(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json({"ok": False, "error": "Thiếu dữ liệu form."}, 400)
            return
        if length > media_transcribe.MAX_UPLOAD_BYTES:
            self._send_json({"ok": False, "error": "File quá lớn (tối đa 512 MB)."}, 413)
            return
        try:
            files = parse_multipart_uploads(
                self.rfile.read(length),
                self.headers.get("Content-Type") or "",
            )
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, 400)
            return
        excel_name, excel_bytes = files.get("excel") or ("", b"")
        audio_name, audio_bytes = files.get("audio") or ("", b"")
        if not excel_bytes:
            for fname, data in files.values():
                lower = fname.lower()
                if lower.endswith((".xlsx", ".xls", ".csv")):
                    excel_name, excel_bytes = fname, data
                elif data and not audio_bytes:
                    audio_name, audio_bytes = fname, data
        if not excel_bytes:
            self._send_json({"ok": False, "error": "Thiếu file Excel hội thoại."}, 400)
            return
        excel_name = Path(excel_name or "gold.xlsx").name
        audio_path = None
        fd, excel_tmp = tempfile.mkstemp(suffix=Path(excel_name).suffix or ".xlsx")
        os.close(fd)
        excel_path = Path(excel_tmp)
        try:
            excel_path.write_bytes(excel_bytes)
            if audio_bytes and audio_name:
                audio_name = Path(audio_name).name
                fd, audio_tmp = tempfile.mkstemp(suffix=Path(audio_name).suffix or ".wav")
                os.close(fd)
                audio_path = Path(audio_tmp)
                audio_path.write_bytes(audio_bytes)
            job_id = ingest_finetune.start_ingest(audio_path, excel_path, audio_name, excel_name)
            self._send_json({"ok": True, "id": job_id})
        except Exception as exc:
            for path in (excel_path, audio_path):
                if path is None:
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            self._send_json({"ok": False, "error": str(exc)}, 500)

    def _finetune_gold(self) -> None:
        qs = parse_qs(urlparse(self.path).query)
        name = unquote((qs.get("name") or [""])[0] or "").strip()
        self._send_json(ingest_finetune.gold_payload_for(name))

    def _finetune_parse(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json({"ok": False, "error": "Thiếu file Excel hội thoại."}, 400)
            return
        if length > 32 * 1024 * 1024:
            self._send_json({"ok": False, "error": "Excel quá lớn."}, 413)
            return
        data = self.rfile.read(length)
        name = self._upload_name()
        lower = name.lower()
        if not lower.endswith((".xlsx", ".xls", ".csv")):
            name = (Path(name).stem or "gold") + ".xlsx"
        qs = parse_qs(urlparse(self.path).query)
        audio_name = unquote((qs.get("audio") or [""])[0] or "").strip()
        fd, tmp = tempfile.mkstemp(suffix=Path(name).suffix or ".xlsx")
        os.close(fd)
        path = Path(tmp)
        try:
            path.write_bytes(data)
            payload = ingest_finetune.parse_excel_payload(path, name, audio_name)
            self._send_json(payload)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 400)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _finetune_seed_glossary(self) -> None:
        try:
            seeded = ingest_finetune.seed_glossary_phrases()
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        payload = dict(seeded)
        payload["stats"] = ingest_finetune.corpus_stats()
        self._send_json(payload)

    def _library_user_get(self) -> None:
        self._send_json({"ok": True, "entries": load_user_library()})

    def _library_user_save(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 512 * 1024:
            self._send_json({"ok": False, "error": "Du lieu editor khong hop le."}, 400)
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "JSON editor khong doc duoc."}, 400)
            return
        rows = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            self._send_json({"ok": False, "error": "Thieu danh sach entries."}, 400)
            return
        try:
            save_user_library(rows)
        except OSError as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return
        self._send_json({"ok": True, "count": len(load_user_library())})

    def _upload_name(self) -> str:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        raw = ""
        if qs.get("name"):
            raw = qs["name"][0]
        if not raw:
            raw = self.headers.get("X-Filename") or "clip.avi"
        name = unquote(raw).replace("\\", "/").split("/")[-1].strip()
        return name or "clip.avi"

    def _query_id(self) -> str:
        qs = parse_qs(urlparse(self.path).query)
        return ((qs.get("id") or [""])[0] or "").strip()

    def _transcode_status(self) -> None:
        media_transcode.sweep_jobs()
        job = media_transcode.job_snapshot(self._query_id())
        if not job:
            self._send_json({"ok": False, "error": "Khong tim thay tien trinh convert."}, 404)
            return
        job["ok"] = True
        self._send_json(job)

    def _transcode_result(self) -> None:
        job_id = self._query_id()
        taken = media_transcode.take_job_file(job_id)
        if taken is None:
            self._send_json({"ok": False, "error": "File convert chua san sang."}, 404)
            return
        path, mime, name = taken
        response_started = False
        try:
            size = path.stat().st_size
            response_started = True
            self.send_response(200)
            self.send_header("Content-Type", mime or "video/mp4")
            self.send_header("Content-Length", str(size))
            self.send_header("X-Playable-Name", name)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                with path.open("rb") as fh:
                    shutil.copyfileobj(fh, self.wfile, length=256 * 1024)
        except (ConnectionError, BrokenPipeError):
            self.close_connection = True
            self.log_message("MP4 download disconnected; result retained for retry")
        except OSError as exc:
            if response_started:
                self.close_connection = True
                self.log_error("MP4 download interrupted: %s", exc)
            else:
                self.send_error(500, str(exc))
        finally:
            media_transcode.release_job_file(job_id)

    def _transcode_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json({"ok": False, "error": "Thieu du lieu file."}, 400)
            return
        if length > media_transcode.MAX_UPLOAD_BYTES:
            self._send_json({"ok": False, "error": "File qua lon (toi da 512 MB)."}, 413)
            return
        suffix = Path(self._upload_name()).suffix or ".avi"
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        src = Path(handle.name)
        started = False
        try:
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                handle.write(chunk)
                remaining -= len(chunk)
            handle.close()
            job_id = media_transcode.start_job(src, self._upload_name())
            started = True
            self._send_json({"ok": True, "id": job_id})
        except OSError as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)
        finally:
            try:
                handle.close()
            except Exception:
                pass
            if not started:
                try:
                    src.unlink(missing_ok=True)
                except OSError:
                    pass


def serve(httpd: ThreadingHTTPServer) -> None:
    httpd.serve_forever()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ATC Symposium Desk local server")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the default browser (for tests / silent start)",
    )
    parser.add_argument("--http-port", type=int, default=HTTP_PORT)
    parser.add_argument("--https-port", type=int, default=HTTPS_PORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    _configure_stdio()
    args = parse_args(argv)
    global ROOT, WEB, CERTS, APK_PATH, APP_VERSION
    ROOT = bundle_root()
    WEB = resolve_web(ROOT)
    CERTS = WEB / "certs"

    os.chdir(WEB)
    version = read_version(ROOT) or read_version(app_home()) or "?"
    APP_VERSION = version
    APK_PATH = resolve_apk(ROOT)
    print("Dang khoi dong ATC Symposium Desk %s..." % version, flush=True)
    print("  created by Lộc đẹp trai", flush=True)
    if not creator_signature_ok(ROOT):
        print("UNG DUNG DA KHOA: SIGNATURE.txt bi thieu hoac bi sua.", flush=True)
    print("  Thu muc app:      %s" % WEB, flush=True)
    db = app_paths.library_sqlite()
    if db.is_file():
        print("  DB thu vien:      %s" % db, flush=True)
    else:
        raise SystemExit("Thieu DB thu vien: %s" % db)
    model = media_transcribe._resolve_model_id()
    print("  Model STT ATC:    %s" % model, flush=True)
    ffmpeg = media_transcode.find_ffmpeg()
    print("  ffmpeg:           %s" % (ffmpeg or "KHONG THAY — khong ghi loi file duoc"), flush=True)
    if APK_PATH is not None:
        print("  APK Android:      %s" % APK_PATH, flush=True)
    threading.Thread(target=media_transcode.warm_encoder, daemon=True).start()
    threading.Thread(target=media_transcribe.warm_model, daemon=True).start()
    ips = lan_ipv4s()
    print("Dang cap chung chi HTTPS cho: %s" % (", ".join(ips) or "localhost"), flush=True)
    certfile, keyfile, ca_cer = ensure_certs(ips)

    http_port = args.http_port
    https_port = args.https_port
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", http_port), DeskHandler)
        httpsd = ThreadingHTTPServer(("0.0.0.0", https_port), DeskHandler)
    except OSError as exc:
        print(
            "Khong mo duoc cong %s/%s (dang dung). Dong cua so CHAY cu, hoac bam lai CHAY.cmd.\n%s"
            % (http_port, https_port, exc),
            flush=True,
        )
        raise SystemExit(2) from exc
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
    httpsd.socket = ctx.wrap_socket(httpsd.socket, server_side=True)

    threading.Thread(target=serve, args=(httpd,), daemon=True).start()
    threading.Thread(target=serve, args=(httpsd,), daemon=True).start()

    pc = "http://127.0.0.1:%s" % http_port
    print("", flush=True)
    print("  ATC Symposium Desk  —  offline iOS / Android", flush=True)
    print("  May nay (PC):     %s" % pc, flush=True)
    print("  HTTPS (dien thoai):", flush=True)
    if ips:
        for ip in ips:
            print("    http://%s:%s/cai-dat.html" % (ip, http_port), flush=True)
            print("    https://%s:%s/" % (ip, https_port), flush=True)
    else:
        print("    (khong thay IPv4 LAN — ket Wi-Fi/hotspot roi mo lai)", flush=True)
    print("  Chung chi CA:     %s" % ca_cer, flush=True)
    if APK_PATH is not None:
        print("  Tai APK Android:  http://127.0.0.1:%s/ATC-Desk-Mobile.apk" % http_port, flush=True)
        if ips:
            print("                    http://%s:%s/ATC-Desk-Mobile.apk" % (ips[0], http_port), flush=True)
    print("  Dien thoai (cung Wi-Fi): mo /cai-dat.html roi ghim PWA (iOS/Android).", flush=True)
    print("  Giu cua so nay mo. Ctrl+C de dung.", flush=True)
    print("", flush=True)
    open_browser = not args.no_browser and os.environ.get("ATC_DESK_NO_BROWSER") != "1"
    if open_browser:
        try:
            webbrowser.open(pc)
        except OSError:
            pass
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nDung server.")


if __name__ == "__main__":
    main()
