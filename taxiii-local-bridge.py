#!/usr/bin/env python3
"""Taxiii read-only localhost bridge.

Security model:
- binds to 127.0.0.1 only
- exposes only /health, /session, /session/clear, /pull and /snapshot
- never persists Firebase credentials
- deliberately has no push/ack/register/revoke endpoint
- credentials are supplied at runtime and kept in RAM only
- rejects stale sessions before an upstream request

This helper does NOT obtain, bypass or forge Firebase Auth/App Check credentials.
Use only short-lived credentials legitimately issued for your own signed-in session.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json, time, re

HOST = "127.0.0.1"
PORT = 8765
UPSTREAM = "https://backup.23.95.165.241.sslip.io"
ALLOWED_ORIGIN = "https://jim850502.github.io"
SESSION_MAX_AGE = 45 * 60
SESSION = {"idToken": None, "appCheck": None, "setAt": None}\nUUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def clear_session():
    SESSION.update(idToken=None, appCheck=None, setAt=None)


def session_age():
    return None if SESSION["setAt"] is None else max(0, int(time.time()) - int(SESSION["setAt"]))


def session_ready():
    age = session_age()
    return bool(SESSION["idToken"] and SESSION["appCheck"] and age is not None and age < SESSION_MAX_AGE)


def reply(h, status, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Cache-Control", "no-store")
    h.send_header("Pragma", "no-cache")
    h.send_header("X-Content-Type-Options", "nosniff")
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
    obj = json.loads(h.rfile.read(n).decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("JSON body must be an object")
    return obj


def validate_sync_body(path, body):
    allowed = {"/v2/sync/pull", "/v2/sync/snapshot"}
    if path not in allowed:
        raise ValueError("upstream endpoint is not read-only")
    device_id = str(body.get("deviceId", "")).strip()
    if not device_id:
        raise ValueError("deviceId required")
    if path.endswith("/pull"):
        cursor = body.get("cursor", 0)
        if not isinstance(cursor, int) or isinstance(cursor, bool) or cursor < 0:
            raise ValueError("cursor must be a non-negative integer")
    else:
        seq = body.get("snapshotSequence")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= 0:
            raise ValueError("snapshotSequence must be a positive integer")
    limit = body.get("limit", 100)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
        raise ValueError("limit must be 1..100")


def upstream(path, body):
    validate_sync_body(path, body)
    if not session_ready():
        clear_session()
        raise RuntimeError("登入工作階段不存在或已過期，請重新取得短效憑證")
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
        try:
            obj = json.loads(text)
        except Exception:
            obj = {"message": text[:500]}
        if e.code in (401, 403):
            clear_session()
        return e.code, obj
    except URLError as e:
        raise RuntimeError("無法連線運轉手同步伺服器") from e


class Handler(BaseHTTPRequestHandler):
    server_version = "TaxiiiReadOnlyBridge/0.3"

    def log_message(self, fmt, *args):
        # Never log request bodies, headers, tokens, or upstream response bodies.
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
            age = session_age()
            return reply(self, 200, {
                "ok": True,
                "version": "0.3",
                "readOnly": True,
                "sessionReady": session_ready(),
                "sessionAgeSeconds": age,
                "sessionMaxAgeSeconds": SESSION_MAX_AGE,
            })
        return reply(self, 404, {"error": "not found"})

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin != ALLOWED_ORIGIN:
            return reply(self, 403, {"error": "origin not allowed"})
        try:
            if self.path == "/session/clear":
                clear_session()
                return reply(self, 200, {"ok": True, "sessionReady": False})
            body = read_json(self)
            if self.path == "/session":
                a = str(body.get("idToken", "")).strip()
                c = str(body.get("appCheck", "")).strip()
                if not a or not c:
                    return reply(self, 400, {"error": "idToken/appCheck required"})
                if len(a) > 8192 or len(c) > 8192:
                    return reply(self, 400, {"error": "credential too large"})
                SESSION.update(idToken=a, appCheck=c, setAt=int(time.time()))
                return reply(self, 200, {"ok": True, "stored": "memory-only", "expiresInSeconds": SESSION_MAX_AGE})
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
    print(f"Taxiii read-only bridge v0.3: http://{HOST}:{PORT}")
    print("Only pull/snapshot are enabled. Credentials remain in RAM and expire locally.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
