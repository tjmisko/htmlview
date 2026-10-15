"""Single-instance handoff for htmlview, with no GTK dependency.

The first htmlview process listens on an abstract Unix socket; later
invocations send it their target and exit, and it opens the target in a new
window whose WebView shares the existing web process. One socket per forced
color scheme, since the scheme is process-wide.

Protocol: the client sends one JSON line {"target": ..., "watch": bool}; the
host answers one line, "ok" or "error: <message>".
"""
import json
import os
import re
import socket
import struct
from urllib.parse import unquote, urlparse

REPLY_TIMEOUT_S = 10
URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MAX_REQUEST_BYTES = 64 * 1024


def socket_name(scheme):
    """Abstract socket address for this user and color scheme (auto/dark/light).

    HTMLVIEW_INSTANCE namespaces it, so tests never reach a user's real host.
    """
    instance = os.environ.get("HTMLVIEW_INSTANCE", "")
    return f"\0htmlview-{os.getuid()}-{scheme}" + (f"-{instance}" if instance else "")


def resolve_target(target, cwd):
    """Return (target to send, error). Paths become absolute; URIs pass through.

    Mirrors Gio.File.new_for_commandline_arg: an existing path wins over a
    scheme-looking string, so `htmlview c:notes.html` still opens the file.
    """
    path = target if os.path.isabs(target) else os.path.join(cwd, target)
    if os.path.exists(path):
        return os.path.normpath(path), None
    if URI_SCHEME.match(target):
        parsed = urlparse(target)
        if parsed.scheme == "file" and not os.path.exists(unquote(parsed.path)):
            return None, f"no such file: {target}"
        return target, None
    return None, f"no such file: {target}"


def send(name, request):
    """Hand a request to a running host.

    Returns the host's reply ("ok" or "error: ..."), or None when no host is
    listening or it went away mid-request, in which case the caller should
    become the host itself.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(REPLY_TIMEOUT_S)
    try:
        sock.connect(name)
        sock.sendall(json.dumps(request).encode() + b"\n")
        reply = sock.makefile("r", encoding="utf-8").readline().strip()
        return reply or None
    except OSError:
        return None
    finally:
        sock.close()


def listen(name):
    """Bind the host socket, or return None if another host already holds it."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(name)
    except OSError:
        sock.close()
        return None
    sock.listen(8)
    return sock


def peer_uid(conn):
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", creds)
    return uid


def serve_one(conn, open_target):
    """Answer one client on an accepted connection.

    open_target(request) opens the window and returns an error string or None.
    Requests from other users are refused: an abstract socket is reachable by
    anyone in the network namespace.
    """
    try:
        conn.settimeout(REPLY_TIMEOUT_S)
        if peer_uid(conn) != os.getuid():
            return
        line = conn.makefile("rb").readline(MAX_REQUEST_BYTES)
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or not isinstance(request.get("target"), str):
                raise ValueError("missing target")
        except ValueError as err:
            conn.sendall(f"error: bad request: {err}\n".encode())
            return
        error = open_target(request)
        conn.sendall(b"ok\n" if error is None else f"error: {error}\n".encode())
    except OSError:
        pass
    finally:
        conn.close()
