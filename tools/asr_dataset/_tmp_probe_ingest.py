"""Temporary probe: POST finetune ingest and print the job result."""
from __future__ import annotations

import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCEL = ROOT / "VJC1225 text.xlsx"
AUDIO = ROOT / "vjc1225.mp4"
BASE = "http://127.0.0.1:8765"


def multipart(fields: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----Boundary" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, filename, data, ctype in fields:
        chunks.append(f"--{boundary}".encode("ascii"))
        disp = f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
        chunks.append(disp.encode("utf-8"))
        chunks.append(f"Content-Type: {ctype}".encode("ascii"))
        chunks.append(b"")
        chunks.append(data)
    chunks.append(f"--{boundary}--".encode("ascii"))
    chunks.append(b"")
    return b"\r\n".join(chunks), boundary


def post(fields: list[tuple[str, str, bytes, str]]) -> dict:
    body, boundary = multipart(fields)
    req = urllib.request.Request(
        BASE + "/api/finetune/ingest",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            print("HTTP", resp.status, raw[:500])
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        print("HTTPError", exc.code, exc.read()[:1000])
        raise


def poll(job_id: str, tries: int = 40) -> dict:
    last = {}
    for i in range(tries):
        with urllib.request.urlopen(BASE + "/api/finetune/job?id=" + job_id, timeout=10) as resp:
            last = json.loads(resp.read())
        print(
            i,
            last.get("percent"),
            last.get("stage"),
            last.get("error"),
            "done",
            last.get("done"),
            "added",
            last.get("gold_added"),
        )
        if last.get("done"):
            return last
        time.sleep(0.5)
    return last


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "excel"
    fields = [
        (
            "excel",
            "VJC1225 text.xlsx",
            EXCEL.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    ]
    if mode == "audio":
        print("audio bytes", AUDIO.stat().st_size)
        fields.append(("audio", "vjc1225.mp4", AUDIO.read_bytes(), "video/mp4"))
    payload = post(fields)
    job_id = payload.get("id")
    if not job_id:
        print("no job id", payload)
        return 1
    job = poll(job_id)
    print("preview", json.dumps(job.get("preview"), ensure_ascii=False)[:800])
    print("learned", job.get("learned"))
    print("error", job.get("error"))
    return 0 if job.get("done") and not job.get("error") else 2


if __name__ == "__main__":
    raise SystemExit(main())
