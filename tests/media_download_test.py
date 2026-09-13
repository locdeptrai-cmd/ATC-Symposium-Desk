"""Disconnected MP4 downloads can be retried without another conversion."""
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import media_transcode as media
import serve


class DownloadTest(unittest.TestCase):
    def test_disconnect_retry_and_expiry(self):
        errors = []
        class Server(ThreadingHTTPServer):
            def handle_error(self, request, client_address):
                errors.append(sys.exc_info()[1])

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.mp4"
            payload = b"test-video" * 1024 * 1024
            path.write_bytes(payload)
            media._JOBS["retry-test"] = {
                "id": "retry-test", "done": True, "path": path,
                "mime": "video/mp4", "name": "test.mp4", "created": time.time()
            }
            server = Server(("127.0.0.1", 0), serve.DeskHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            route = "/api/media/transcode/result?id=retry-test"
            try:
                sock = socket.create_connection(("127.0.0.1", port))
                sock.sendall(("GET " + route + " HTTP/1.1\r\nHost: localhost\r\n\r\n").encode())
                self.assertIn(b"200", sock.recv(1024))
                linger = struct.pack("hh" if sys.platform == "win32" else "ii", 1, 0)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
                sock.close()
                for _ in range(100):
                    if not media._JOBS["retry-test"].get("readers"):
                        break
                    time.sleep(.02)
                self.assertFalse(errors, errors)
                self.assertTrue(path.is_file())
                for _ in range(2):
                    conn = HTTPConnection("127.0.0.1", port, timeout=10)
                    conn.request("GET", route)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), payload)
                    conn.close()
                media.take_job_file("retry-test")
                media.sweep_jobs(max_age=-1)
                self.assertTrue(path.is_file(), "Do not expire an active download")
                media.release_job_file("retry-test")
                media.sweep_jobs(max_age=-1)
                self.assertFalse(path.exists())
                self.assertFalse(errors, errors)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                media._JOBS.pop("retry-test", None)


if __name__ == "__main__":
    unittest.main()
