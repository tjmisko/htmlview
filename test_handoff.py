#!/usr/bin/env python3
"""Display-free tests for handoff.py. Run: python3 test_handoff.py"""
import os
import socket
import tempfile
import threading
import unittest
import uuid
from unittest import mock

from handoff import listen, resolve_target, send, serve_one, socket_name


def unique_name():
    return f"\0htmlview-test-{uuid.uuid4().hex}"


class ResolveTargetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.page = os.path.join(self.tmp.name, "page.html")
        open(self.page, "w").close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_should_make_path_absolute_when_relative_to_cwd(self):
        self.assertEqual(resolve_target("page.html", self.tmp.name), (self.page, None))

    def test_should_keep_absolute_path_when_file_exists(self):
        self.assertEqual(resolve_target(self.page, "/"), (self.page, None))

    def test_should_report_missing_file_when_path_does_not_exist(self):
        target, error = resolve_target("nope.html", self.tmp.name)
        self.assertIsNone(target)
        self.assertIn("no such file", error)

    def test_should_pass_url_through_when_scheme_is_http(self):
        self.assertEqual(resolve_target("https://example.com/x", "/"),
                         ("https://example.com/x", None))

    def test_should_report_missing_file_when_file_uri_does_not_exist(self):
        _, error = resolve_target("file:///nonexistent/page.html", "/")
        self.assertIn("no such file", error)

    def test_should_accept_file_uri_when_file_exists(self):
        uri = "file://" + self.page.replace(" ", "%20")
        self.assertEqual(resolve_target(uri, "/"), (uri, None))

    def test_should_prefer_existing_path_when_name_looks_like_a_scheme(self):
        odd = os.path.join(self.tmp.name, "c:notes.html")
        open(odd, "w").close()
        self.assertEqual(resolve_target("c:notes.html", self.tmp.name), (odd, None))

    def test_should_resolve_unicode_and_spaces_when_present_in_path(self):
        page = os.path.join(self.tmp.name, "ünï côde.html")
        open(page, "w").close()
        self.assertEqual(resolve_target("ünï côde.html", self.tmp.name), (page, None))


class SocketNameTests(unittest.TestCase):
    def test_should_differ_when_scheme_differs(self):
        self.assertNotEqual(socket_name("auto"), socket_name("dark"))

    def test_should_be_abstract_when_built(self):
        self.assertTrue(socket_name("auto").startswith("\0"))

    def test_should_namespace_when_instance_is_set(self):
        with mock.patch.dict(os.environ, {"HTMLVIEW_INSTANCE": "t1"}):
            namespaced = socket_name("auto")
        with mock.patch.dict(os.environ, {"HTMLVIEW_INSTANCE": ""}):
            plain = socket_name("auto")
        self.assertNotEqual(namespaced, plain)
        self.assertTrue(namespaced.endswith("-t1"))


class HandoffTests(unittest.TestCase):
    def serve(self, name, open_target, count=1):
        sock = listen(name)
        self.assertIsNotNone(sock)

        def run():
            for _ in range(count):
                conn, _ = sock.accept()
                serve_one(conn, open_target)
            sock.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def test_should_return_none_when_no_host_is_listening(self):
        self.assertIsNone(send(unique_name(), {"target": "/x"}))

    def test_should_deliver_request_and_reply_ok_when_host_opens_it(self):
        name, seen = unique_name(), []
        thread = self.serve(name, lambda req: seen.append(req))
        self.assertEqual(send(name, {"target": "/a.html", "watch": True}), "ok")
        thread.join(5)
        self.assertEqual(seen, [{"target": "/a.html", "watch": True}])

    def test_should_relay_error_when_host_cannot_open_target(self):
        name = unique_name()
        thread = self.serve(name, lambda _req: "no such file: /a.html")
        self.assertEqual(send(name, {"target": "/a.html"}), "error: no such file: /a.html")
        thread.join(5)

    def test_should_reply_error_when_request_has_no_target(self):
        name = unique_name()
        thread = self.serve(name, lambda _req: None)
        self.assertTrue(send(name, {"watch": True}).startswith("error: bad request"))
        thread.join(5)

    def test_should_reply_error_when_request_is_not_json(self):
        name, opened = unique_name(), []
        thread = self.serve(name, lambda req: opened.append(req))
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(name)
        client.sendall(b"not json\n")
        reply = client.makefile("r").readline()
        client.close()
        thread.join(5)
        self.assertTrue(reply.startswith("error: bad request"))
        self.assertEqual(opened, [])

    def test_should_refuse_second_listener_when_name_is_taken(self):
        name = unique_name()
        first = listen(name)
        try:
            self.assertIsNone(listen(name))
        finally:
            first.close()

    def test_should_return_none_when_host_closes_without_reply(self):
        name = unique_name()
        sock = listen(name)

        def drop():
            conn, _ = sock.accept()
            conn.close()
            sock.close()

        thread = threading.Thread(target=drop, daemon=True)
        thread.start()
        self.assertIsNone(send(name, {"target": "/a.html"}))
        thread.join(5)

    def test_should_ignore_client_when_peer_uid_differs(self):
        name, opened = unique_name(), []
        with mock.patch("handoff.peer_uid", return_value=os.getuid() + 1):
            thread = self.serve(name, lambda req: opened.append(req))
            self.assertIsNone(send(name, {"target": "/a.html"}))
            thread.join(5)
        self.assertEqual(opened, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
