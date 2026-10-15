# htmlview

A bare WebKitGTK window for viewing local HTML/JS files without a browser.

No tabs, no URL bar, no browser profile, no extensions: one Python script
(plus small key-map and handoff modules) on top of libraries your distribution
already ships. Built for rendering generated
HTML artifacts (e.g. from Claude Code) that use `fetch()` and ES modules,
which browsers refuse to run from `file://`.

```
htmlview page.html            # local file
htmlview -w page.html         # reload whenever the file changes
htmlview --light page.html    # force a color scheme (--dark / --light)
htmlview https://example.com  # any URL
cat page.html | htmlview -    # read HTML from stdin
htmlview --separate page.html # independent process (implied by -)
```

The first window opens in about 0.4 s; later ones in about 0.15 s, since they
join the running process.

## Install

Requirements: Python 3, PyGObject, GTK 4, WebKitGTK 6.0.

```
# Fedora
sudo dnf install python3-gobject gtk4 webkitgtk6.0
# Debian / Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0
# Arch
sudo pacman -S python-gobject gtk4 webkitgtk-6.0
```

Then put the script on your `PATH`:

```
git clone https://github.com/tjmisko/htmlview.git
ln -s "$PWD/htmlview/htmlview" ~/.local/bin/htmlview
```

## Keys

| Key                   | Action                                |
| --------------------- | ------------------------------------- |
| `q` `Ctrl-W` `Ctrl-Q` | quit                                  |
| `r` `F5`              | reload (`Ctrl-R` bypasses the cache)  |
| `+` `-` `0`           | zoom in / out / reset (also with `Ctrl`) |
| `[` `]`               | back / forward                        |
| `F12` `Ctrl-Shift-I`  | web inspector                         |
| `j` `k`               | scroll down / up by 60px              |
| `PgUp` `PgDn`         | scroll up / down by half a page       |
| `gg` `G`              | scroll to top / bottom                |
| `Ctrl-Up` `Ctrl-Down` | previous / next section (the page's table of contents, else `h1`–`h3`) |
| `/`                   | search (incremental, smartcase)       |
| `n` `N`               | next / previous match                 |
| `Esc`                 | clear search highlights               |

In the search bar, `Enter` closes it but keeps highlights and the query (then
`n` / `N` step through matches); `Esc` closes it and clears highlights. Search
is case-insensitive unless the query contains an uppercase letter.

Single-letter keys are suppressed while an `<input>`, `<textarea>`, or
contenteditable element or the search bar has focus, so typing `q` into a form field does not
close the window. Modifier bindings always work.

## Behaviour

- **`file://` is unrestricted.** `fetch()`, `XMLHttpRequest`, and ES module
  imports work against sibling files. Real browsers block these, which is the
  usual reason a generated page renders blank when opened directly.
- **Color scheme** follows the system (`org.gnome.desktop.interface
  color-scheme`, or a `*-dark` `gtk-theme`, as GTK itself does). Override with
  `--dark` / `--light`. In dark mode the view background is painted dark before
  first load, so there is no white flash.
- **Links.** When viewing a local file, clicking an `http(s)` link opens it in
  your default browser; navigation between local files stays in the window.
  Popups (`target=_blank`, `window.open`) always go to the browser. When given
  a URL, htmlview behaves like a plain browser.
- **Console output.** `console.log` and uncaught errors are echoed to stderr.
  The web process buffers this when stderr is a pipe, so redirected output
  arrives on exit.
- **One window per invocation, one engine for all of them.** The first
  `htmlview` becomes the host; later invocations hand their target to it over
  a Unix socket and exit, and it opens a new window that shares its WebKit web
  and network processes. The first window costs about 110 MiB of private
  memory; each further window about 10 MiB. The host exits when its last
  window closes. Windows forced to `--dark` or `--light` get a host of their
  own (the color scheme is process-wide), and `--separate` opens a fully
  independent process, whose page console output stays on its own stderr.
  One page crashing the web process takes the windows sharing it down too.
  The Wayland `app_id` / X11 class is `htmlview`, for compositor window rules.- **Site data** (`localStorage`, cache) is kept under
  `~/.local/share/htmlview/` and `~/.cache/htmlview/`, so a page's remembered
  state survives between runs. Delete those directories to reset.
- **Ctrl-C** in the terminal quits cleanly.

## Tests

```
python3 test_keys.py      # key bindings, no display needed
python3 test_handoff.py   # single-instance handoff, no display needed
python3 test_htmlview.py
```

Each `test_htmlview.py` test launches a real window for a few seconds, interrupts it, and checks
the console output emitted by `examples/hello.html`. A running Wayland or X
session is required; no extra test dependencies.

## Troubleshooting

**`Cannot get portal org.freedesktop.portal.Settings ... startup job failed`
on stderr.** GTK could not reach `xdg-desktop-portal`, so it falls back to
GSettings; the page still renders. On a compositor started bare from a TTY the
cause is usually that nothing activated `graphical-session.target` in your
user session, and the portal service refuses to start without it
(`Requisite=graphical-session.target`). Start your compositor through
`uwsm`, or have it start a target that binds to `graphical-session.target`
after exporting `WAYLAND_DISPLAY` with `dbus-update-activation-environment
--systemd`.

**Page is light although the system is dark (or vice versa).** Pass
`--dark` / `--light`. Auto mode reads GSettings, which may differ from what a
non-GNOME desktop configures elsewhere.

**Rendering glitches on unusual GPUs.** Try `WEBKIT_DISABLE_DMABUF_RENDERER=1
htmlview page.html`, and if that helps, `WEBKIT_DISABLE_COMPOSITING_MODE=1`.

## How it works

`htmlview` is a single `Gtk.Application` holding one `WebKit.WebView`. A
`Gtk.EventControllerKey` in the capture phase handles the key bindings before
the view sees them; a small user script posts focus changes back over
`webkit.messageHandlers` so bindings can step aside while you type. `-w` uses
a `Gio.FileMonitor` with a short debounce. `--dark`/`--light` set `GTK_THEME`
before GTK initialises, which is what stops GTK re-syncing the color scheme
from the system.
