"""Display-free key interpretation for htmlview.

KeyDispatcher maps (GDK key name, modifiers, context) to an action string; the
viewer performs the action. No GTK import, so it is unit-testable anywhere.
"""

GG_TIMEOUT_MS = 1000

# Modifier-guarded bindings that work everywhere, even while typing.
CTRL_ACTIONS = {
    "q": "quit",
    "w": "quit",
    "r": "reload_bypass_cache",
    "plus": "zoom_in",
    "equal": "zoom_in",
    "minus": "zoom_out",
    "0": "zoom_reset",
}
ALWAYS_ACTIONS = {"F5": "reload", "F12": "inspector"}

# Ctrl-modified navigation, suppressed while typing (Ctrl-Up/Down move by
# paragraph in text fields).
CTRL_NAV_ACTIONS = {"Down": "section_next", "Up": "section_prev"}

# Plain single-letter bindings, suppressed while typing.
PLAIN_ACTIONS = {
    "q": "quit",
    "r": "reload",
    "plus": "zoom_in",
    "equal": "zoom_in",
    "minus": "zoom_out",
    "0": "zoom_reset",
    "bracketleft": "back",
    "bracketright": "forward",
    "j": "scroll_down",
    "k": "scroll_up",
    "G": "bottom",
    "Page_Down": "half_page_down",
    "Page_Up": "half_page_up",
    "slash": "search_open",
    "n": "search_next",
    "N": "search_prev",
    "Escape": "clear_search",
}


def smartcase_insensitive(query):
    """Vim smartcase: search case-insensitively unless the query has uppercase."""
    return query == query.lower()


class KeyDispatcher:
    def __init__(self):
        self.g_pending_since = None

    def dispatch(self, key, ctrl, shift, now_ms, editable_focus, search_focused):
        """Return an action string, or None to leave the key unhandled."""
        pending_since, self.g_pending_since = self.g_pending_since, None

        if ctrl:
            if shift and key in ("I", "i"):
                return "inspector"
            if key in CTRL_NAV_ACTIONS:
                if editable_focus or search_focused:
                    return None
                return CTRL_NAV_ACTIONS[key]
            return CTRL_ACTIONS.get(key)
        if key in ALWAYS_ACTIONS:
            return ALWAYS_ACTIONS[key]

        if search_focused:
            return "search_close" if key == "Escape" else None
        if editable_focus:
            return None

        if key == "g":
            if pending_since is not None and now_ms - pending_since <= GG_TIMEOUT_MS:
                return "top"
            self.g_pending_since = now_ms
            return "g_pending"
        return PLAIN_ACTIONS.get(key)
