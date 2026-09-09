"""Локальный сервер с поддержкой HTTP Range.

Без Range браузер не может перематывать видео: video.seekable пустой,
и скролл по ролику не работает. Штатный python -m http.server
Range не поддерживает, поэтому нужен этот файл.

    python serve.py 5174
"""
import http.server, os, re, socketserver, sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5174
ROOT = os.path.dirname(os.path.abspath(__file__))


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()

        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()

        size = os.path.getsize(path)
        start_s, end_s = m.group(1), m.group(2)
        if start_s:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        else:                                   # суффиксный диапазон: bytes=-500
            start = max(0, size - int(end_s))
            end = size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416)
            return None

        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        return _Slice(f, end - start + 1)


class _Slice:
    """Отдаёт ровно N байт из файла."""
    def __init__(self, f, remaining):
        self.f, self.remaining = f, remaining

    def read(self, n=-1):
        if self.remaining <= 0:
            return b""
        if n < 0 or n > self.remaining:
            n = self.remaining
        data = self.f.read(n)
        self.remaining -= len(data)
        return data

    def close(self):
        self.f.close()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


print(f"Range server on http://localhost:{PORT} (root: {ROOT})", flush=True)
Server(("127.0.0.1", PORT), RangeHandler).serve_forever()
