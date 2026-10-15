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
import uuid

HERE = pathlib.Path(__file__).resolve().parent
HTMLVIEW = HERE / "htmlview"
FIXTURE = HERE / "examples" / "hello.html"
SETTLE_SECONDS = 3.0
HANDOFF_MAX_SECONDS = 2.0

# A private handoff socket per test run, so tests never hand pages to (or
# receive them from) an htmlview the user has open.
os.environ["HTMLVIEW_INSTANCE"] = f"test-{uuid.uuid4().hex[:8]}"


def web_processes(pid):
    """WebKit web content processes descended from pid."""
    children = {}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            ppid = int((proc / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        children.setdefault(ppid, []).append(proc)
    found, stack = [], [pid]
    while stack:
        for child in children.get(stack.pop(), []):
            stack.append(int(child.name))
            try:
                if (child / "comm").read_text().strip().startswith("WebKitWebProces"):
                    found.append(int(child.name))
            except OSError:
                pass
    return found


def write_page(directory, marker):
    page = pathlib.Path(directory) / f"{marker}.html"
    page.write_text(f"<title>{marker}</title><script>console.log('{marker}')</script>")
    return page


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

    def test_should_open_second_target_in_running_host_when_one_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = write_page(tmp, "SHARED_FIRST"), write_page(tmp, "SHARED_SECOND")
            host = subprocess.Popen([str(HTMLVIEW), str(first)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(SETTLE_SECONDS)
            start = time.monotonic()
            client = subprocess.run([str(HTMLVIEW), str(second)],
                                    capture_output=True, text=True, timeout=10)
            handoff_seconds = time.monotonic() - start
            time.sleep(SETTLE_SECONDS)
            web = web_processes(host.pid)
            host.send_signal(signal.SIGINT)
            _, err = host.communicate(timeout=10)

        self.assertEqual(client.returncode, 0, client.stderr)
        self.assertLess(handoff_seconds, HANDOFF_MAX_SECONDS)
        self.assertIn("SHARED_FIRST", err)
        self.assertIn("SHARED_SECOND", err)  # rendered by the host, not the client
        self.assertEqual(len(web), 1, "both windows should share one web process")

    def assert_stays_independent(self, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = write_page(tmp, "HOST"), write_page(tmp, "OTHER")
            host = subprocess.Popen([str(HTMLVIEW), str(first)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(SETTLE_SECONDS)
            other = subprocess.Popen([str(HTMLVIEW), *extra, str(second)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(HANDOFF_MAX_SECONDS + 1)
            still_running = other.poll() is None
            for proc in (other, host):
                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=10)
        self.assertTrue(still_running, "expected its own process, not a handoff")

    def test_should_start_own_process_when_separate_flag_given(self):
        self.assert_stays_independent("--separate")

    def test_should_start_own_host_when_color_scheme_differs(self):
        self.assert_stays_independent("--dark")

    def test_should_print_usage_when_no_target_given(self):
        proc = subprocess.run([str(HTMLVIEW)], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
