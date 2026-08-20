# htmlview

Bare WebKitGTK window for viewing local HTML/JS artifacts (e.g. Claude Code
artifacts) without a browser: no tabs, no URL bar, no browser profile. One
Python file on top of libraries Fedora already ships.

```
htmlview page.html            # local file
htmlview -w page.html         # reload on save
htmlview https://example.com  # any URL
cat page.html | htmlview -    # stdin
```

## Install

```
sudo dnf install python3-gobject gtk4 webkitgtk6.0
ln -sfn ~/Tools/htmlview/htmlview ~/.local/bin/htmlview
```

## Keys

| Key                  | Action                              |
| -------------------- | ----------------------------------- |
| `q` `Ctrl-W` `Ctrl-Q`| quit                                |
| `r` `F5`             | reload (`Ctrl-R` bypasses cache)    |
| `+` `-` `0`          | zoom in / out / reset (also `Ctrl-`)|
| `[` `]`              | back / forward                      |
| `F12` `Ctrl-Shift-I` | web inspector                       |

Single-letter keys are suppressed while an `<input>`, `<textarea>`, or
contenteditable has focus, so typing `q` in a form field does not close the
window. Modifier bindings always work.

## Behaviour

- `fetch()` and ES module imports work from `file://`. Real browsers block
  these, which is the usual reason an artifact renders blank when opened
  directly.
- `prefers-color-scheme` follows `org.gnome.desktop.interface color-scheme`
  (or a `*-dark` `gtk-theme`, as GTK itself does); override with `--dark` /
  `--light` (implemented by setting `GTK_THEME`,
  which is what stops GTK re-syncing the scheme from the system). In dark
  mode the view background is set dark before first paint, so there is no
  white flash.
- When viewing a local file, clicking an `http(s)` link opens it in the default
  browser (`xdg-open`); local navigation stays in-view. Popups always go
  external. When given a URL, htmlview behaves like a plain browser.
- Page console output (`console.log`, uncaught errors) is echoed to stderr
  (WebKit's `enable-write-console-messages-to-stdout`, despite the name). The
  web process buffers it when stderr is a pipe, so it lands on exit.
- Each invocation is its own process and window (`NON_UNIQUE`), so several
  files can be open at once and the Wayland `app_id` is `htmlview` for window
  rules.
- Site data (`localStorage`, cache) lives under `~/.local/share/htmlview/`
  and `~/.cache/htmlview/`, so an artifact's remembered state survives
  between runs. Delete those directories to reset.

## Tests

```
python3 test_htmlview.py
```

Each test opens a real window for a few seconds, sends SIGINT, and reads the
console output the fixture (`examples/hello.html`) emits. Needs a running
Wayland/X session.

## Notes

Portal warnings on stderr (`Cannot get portal org.freedesktop.portal.Settings`)
mean `xdg-desktop-portal` is not running. That is a session problem, not an
htmlview one: the portal has `Requisite=graphical-session.target`, and a
compositor launched bare from a TTY never starts that target. See
`~/.config/systemd/user/hyprland-session.target` and the `hyprland.start`
hook in `~/.config/hypr/hyprland.lua` for the fix used here.
