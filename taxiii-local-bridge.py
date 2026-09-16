#!/usr/bin/env python3
"""Taxiii read-only localhost bridge.

Security model:
- binds to 127.0.0.1 only
- exposes only /health, /session, /pull and /snapshot
- never persists Firebase credentials
- deliberately has no push/ack/register/revoke endpoint
- credentials are supplied to /session at runtime and kept in RAM only

This helper does NOT obtain, bypass or forge Firebase/Auth/App Check credentials.
Use only credentials legitimately issued for your own signed-in session.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json, time

HOST = "127.0.0.1"
PORT = 8765
UPSTREAM = "https://backup.23.95.165.241.sslip.io"
ALLOWED_ORIGIN = "https://jim850502.github.io"
SESSION = {"idToken": None, "appCheck": None, "setAt": None}


def reply(h, status, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Cache-Control", "no-store")
    origin = h.headers.get("Origin")
    if origin == ALLOWED_ORIGIN:
        h.send_header("Access-Control-Allow-Origin", origin)
        h.send_header("Vary", "Origin")
    h.end_headers()
    h.wfile.write(data)


def read_json(h):
    n = int(h.headers.get("Content-Length", "0") or 0)
    if n <= 0 or n > 1024 * 1024:
        raise ValueError("invalid body size")
    return json.loads(h.rfile.read(n).decode("utf-8"))


def upstream(path, body):
    if not SESSION["idToken"] or not SESSION["appCheck"]:
        raise RuntimeError("尚未設定目前登入工作階段憑證")
    raw = json.dumps(body, separators=(",", ":")).encode()
    req = Request(UPSTREAM + path, data=raw, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + SESSION["idToken"],
        "X-Firebase-AppCheck": SESSION["appCheck"],
    })
    try:
        with urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try: obj = json.loads(text)
        except Exception: obj = {"message": text[:500]}
        return e.code, obj


class Handler(BaseHTTPRequestHandler):
    server_version = "TaxiiiReadOnlyBridge/0.1"

    def log_message(self, fmt, *args):
        # Never log request bodies or credentials.
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if origin != ALLOWED_ORIGIN:
            return reply(self, 403, {"error": "origin not allowed"})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            return reply(self, 200, {"ok": True, "readOnly": True, "sessionReady": bool(SESSION["idToken"] and SESSION["appCheck"])})
        return reply(self, 404, {"error": "not found"})

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin != ALLOWED_ORIGIN:
            return reply(self, 403, {"error": "origin not allowed"})
        try:
            body = read_json(self)
            if self.path == "/session":
                a = str(body.get("idToken", "")).strip()
                c = str(body.get("appCheck", "")).strip()
                if not a or not c:
                    return reply(self, 400, {"error": "idToken/appCheck required"})
                SESSION.update(idToken=a, appCheck=c, setAt=int(time.time()))
                return reply(self, 200, {"ok": True, "stored": "memory-only"})
            if self.path == "/pull":
                status, obj = upstream("/v2/sync/pull", body)
                return reply(self, status, obj)
            if self.path == "/snapshot":
                status, obj = upstream("/v2/sync/snapshot", body)
                return reply(self, status, obj)
            return reply(self, 404, {"error": "read-only endpoint not found"})
        except Exception as e:
            return reply(self, 400, {"error": str(e)})


if __name__ == "__main__":
    print(f"Taxiii read-only bridge: http://{HOST}:{PORT}")
    print("Only pull/snapshot are enabled. Credentials remain in RAM.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
