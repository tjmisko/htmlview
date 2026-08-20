#!/usr/bin/env python3
"""Behavioral tests for htmlview. Each test opens a real window briefly.

Run: python3 test_htmlview.py
"""
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
HTMLVIEW = HERE / "htmlview"
FIXTURE = HERE / "examples" / "hello.html"
SETTLE_SECONDS = 3.0


def run_htmlview(*args, stdin=None, seconds=SETTLE_SECONDS, before_quit=None):
    """Run htmlview for `seconds`, then Ctrl-C it and collect flushed output.

    WebKit echoes page console output on stderr and the web process buffers it
    when stderr is a pipe, so the lines only arrive once the app exits cleanly.
    """
    proc = subprocess.Popen(
        [str(HTMLVIEW), *args],
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if stdin is not None:
        proc.stdin.write(stdin)
        proc.stdin.close()
    time.sleep(seconds)
    if before_quit is not None:
        before_quit()
        time.sleep(seconds)
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
    try:
        out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return proc.returncode, out, err


@unittest.skipUnless(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"),
                     "needs a display")
class HtmlviewTests(unittest.TestCase):
    def test_should_run_js_fetch_and_module_imports_from_a_local_file(self):
        code, _, err = run_htmlview(str(FIXTURE))
        self.assertEqual(code, 0, err)
        self.assertIn("HTMLVIEW_TEST fetch=ok 42", err)
        self.assertIn("HTMLVIEW_TEST module=ok", err)
        self.assertIn("HTMLVIEW_TEST done", err)

    def test_should_emit_only_page_console_lines_on_stderr(self):
        _, _, err = run_htmlview(str(FIXTURE))
        noise = [line for line in err.splitlines() if "CONSOLE" not in line]
        self.assertEqual(noise, [], err)

    def test_should_force_color_scheme_when_flag_given(self):
        _, _, dark_err = run_htmlview("--dark", str(FIXTURE))
        _, _, light_err = run_htmlview("--light", str(FIXTURE))
        self.assertIn("HTMLVIEW_TEST scheme=dark", dark_err)
        self.assertIn("HTMLVIEW_TEST scheme=light", light_err)

    def test_should_render_html_from_stdin_when_target_is_dash(self):
        html = "<script>console.log('HTMLVIEW_STDIN ok')</script>"
        code, _, err = run_htmlview("-", stdin=html)
        self.assertEqual(code, 0, err)
        self.assertIn("HTMLVIEW_STDIN ok", err)

    def test_should_reload_when_watched_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("hello.html", "data.json", "mod.js"):
                shutil.copy(FIXTURE.parent / name, tmp)
            page = pathlib.Path(tmp) / "hello.html"

            def edit_page():
                page.write_text(page.read_text().replace(
                    "HTMLVIEW_TEST done", "HTMLVIEW_TEST done-v2"))

            code, _, err = run_htmlview("-w", str(page), before_quit=edit_page)
        self.assertEqual(code, 0, err)
        self.assertIn("HTMLVIEW_TEST done\n", err)
        self.assertIn("HTMLVIEW_TEST done-v2", err)

    def test_should_fail_fast_when_file_is_missing(self):
        start = time.monotonic()
        proc = subprocess.run([str(HTMLVIEW), "/nonexistent/page.html"],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no such file", proc.stderr)
        self.assertLess(time.monotonic() - start, 5)

    def test_should_print_usage_when_no_target_given(self):
        proc = subprocess.run([str(HTMLVIEW)], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
