#!/usr/bin/env python3
"""Display-free tests for keys.py. Run: python3 test_keys.py"""
import unittest

from keys import GG_TIMEOUT_MS, KeyDispatcher, smartcase_insensitive


def press(d, key, now=0, ctrl=False, shift=False, editable=False, search=False):
    return d.dispatch(key, ctrl, shift, now, editable, search)


class KeyDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.d = KeyDispatcher()

    def test_should_scroll_when_j_k_pressed(self):
        self.assertEqual(press(self.d, "j"), "scroll_down")
        self.assertEqual(press(self.d, "k"), "scroll_up")

    def test_should_go_to_bottom_when_G_pressed(self):
        self.assertEqual(press(self.d, "G", shift=True), "bottom")

    def test_should_go_to_top_when_g_pressed_twice_within_a_second(self):
        press(self.d, "g", now=1000)
        self.assertEqual(press(self.d, "g", now=1000 + GG_TIMEOUT_MS), "top")

    def test_should_not_go_to_top_when_second_g_comes_after_timeout(self):
        press(self.d, "g", now=1000)
        self.assertNotEqual(press(self.d, "g", now=1000 + GG_TIMEOUT_MS + 1), "top")

    def test_should_make_second_g_pending_when_first_expired(self):
        press(self.d, "g", now=0)
        press(self.d, "g", now=5000)
        self.assertEqual(press(self.d, "g", now=5100), "top")

    def test_should_scroll_and_clear_pending_when_g_then_j(self):
        press(self.d, "g", now=0)
        self.assertEqual(press(self.d, "j", now=100), "scroll_down")
        self.assertNotEqual(press(self.d, "g", now=200), "top")

    def test_should_clear_pending_when_third_g_follows_gg(self):
        press(self.d, "g", now=0)
        press(self.d, "g", now=10)
        self.assertNotEqual(press(self.d, "g", now=20), "top")

    def test_should_ignore_letters_when_editable_focused(self):
        for key in "jkgGnNqr":
            self.assertIsNone(press(self.d, key, editable=True), key)
        self.assertIsNone(press(self.d, "slash", editable=True))
        self.assertIsNone(press(self.d, "Escape", editable=True))

    def test_should_ignore_letters_when_search_focused(self):
        for key in "jkgGnNqr":
            self.assertIsNone(press(self.d, key, search=True), key)
        self.assertIsNone(press(self.d, "slash", search=True))

    def test_should_close_search_when_escape_in_search_entry(self):
        self.assertEqual(press(self.d, "Escape", search=True), "search_close")

    def test_should_not_arm_gg_when_g_typed_in_editable(self):
        press(self.d, "g", now=0, editable=True)
        self.assertNotEqual(press(self.d, "g", now=10), "top")

    def test_should_not_trigger_scroll_or_gg_when_ctrl_held(self):
        for key in "jkgGn":
            self.assertIsNone(press(self.d, key, ctrl=True), key)
        press(self.d, "g", now=0, ctrl=True)
        self.assertNotEqual(press(self.d, "g", now=10), "top")

    def test_should_open_search_when_slash_pressed(self):
        self.assertEqual(press(self.d, "slash"), "search_open")

    def test_should_emit_next_prev_when_n_N_pressed(self):
        self.assertEqual(press(self.d, "n"), "search_next")
        self.assertEqual(press(self.d, "N", shift=True), "search_prev")

    def test_should_clear_search_when_escape_outside_editable(self):
        self.assertEqual(press(self.d, "Escape"), "clear_search")

    def test_should_keep_existing_plain_bindings(self):
        expected = {
            "q": "quit", "r": "reload", "bracketleft": "back",
            "bracketright": "forward", "plus": "zoom_in", "equal": "zoom_in",
            "minus": "zoom_out", "0": "zoom_reset",
        }
        for key, action in expected.items():
            self.assertEqual(press(self.d, key), action, key)

    def test_should_keep_existing_ctrl_and_function_bindings(self):
        self.assertEqual(press(self.d, "q", ctrl=True), "quit")
        self.assertEqual(press(self.d, "w", ctrl=True), "quit")
        self.assertEqual(press(self.d, "r", ctrl=True), "reload_bypass_cache")
        self.assertEqual(press(self.d, "plus", ctrl=True), "zoom_in")
        self.assertEqual(press(self.d, "minus", ctrl=True), "zoom_out")
        self.assertEqual(press(self.d, "0", ctrl=True), "zoom_reset")
        self.assertEqual(press(self.d, "I", ctrl=True, shift=True), "inspector")
        self.assertEqual(press(self.d, "F5"), "reload")
        self.assertEqual(press(self.d, "F12"), "inspector")

    def test_should_keep_always_on_bindings_when_typing(self):
        for kw in ({"editable": True}, {"search": True}):
            self.assertEqual(press(self.d, "F5", **kw), "reload")
            self.assertEqual(press(self.d, "q", ctrl=True, **kw), "quit")

    def test_should_return_none_when_key_unbound(self):
        self.assertIsNone(press(self.d, "x"))
        self.assertIsNone(press(self.d, None))


class SmartcaseTests(unittest.TestCase):
    def test_should_be_insensitive_when_query_all_lowercase(self):
        self.assertTrue(smartcase_insensitive("foo"))

    def test_should_be_sensitive_when_query_has_uppercase(self):
        self.assertFalse(smartcase_insensitive("Foo"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
