Issue for charmbracelet/gum, posted 2026-10-19 as https://github.com/charmbracelet/gum/issues/1172

Title: `gum confirm` exits 0 (affirmative) when it receives SIGTERM

### Description

When `gum confirm` receives SIGTERM, it exits with whichever answer is selected. The default selection is the affirmative one, so an untouched prompt that is terminated exits 0, and `gum confirm "..." && <action>` runs an action nobody confirmed.

We hit this with a real script. Omarchy's `omarchy-update-restart` (v4.0.5 and v4.0.6) contains `gum confirm "$1" && { omarchy-system-reboot; exit 0; }`. During a headless update on two test VMs, our own watchdog sent SIGTERM to the waiting prompt, and both VMs rebooted.

To reproduce (`script` supplies the TTY):

```sh
script -qfc "gum confirm 'Delete everything?'; echo rc=\$?" /dev/null &
sleep 1; kill -TERM "$(pgrep -n -x gum)"; wait
```

| Command | Signal | Exit code |
| --- | --- | --- |
| `gum confirm` | SIGTERM | 0 |
| `gum confirm --default=false` | SIGTERM | 1 |
| `gum confirm --affirmative=Reboot --negative=Cancel` | SIGTERM | 0 |
| `gum confirm` | SIGINT | 130 |
| `gum confirm` | SIGHUP | 129 (default signal handling, not a gum code path) |
| `gum choose a b c`, `gum choose --selected=b a b c` | SIGTERM | 1 |
| `gum input --value=preset`, `gum write --value=preset`, `gum filter a b c` | SIGTERM | 1 |

Expected: a terminated `confirm` reports that nobody answered, as the other prompt commands already do. They exit 1. Either 1 or 130 (`exit.StatusAborted`, what Ctrl+C already returns) would make `&&` safe.

Cause, from the source: bubbletea's `handleSignals` (v2.0.10, `tea.go`) turns SIGINT into `InterruptMsg` and SIGTERM into `QuitMsg`. `QuitMsg` makes the event loop return the model and a nil error, and `Run` returns that nil error. That graceful quit is deliberate, from bubbletea #412, so the terminal is restored. `choose`, `input`, `write` and `filter` then check `m.submitted` and fail when nothing was submitted. `confirm/command.go` has no such check. It passes a `Run` error through unless the deadline expired, and otherwise turns `m.confirmation`, which starts as `--default` (true), into exit 0 or 1.

Its model already sets `quitting = true` on Enter, Esc and the affirmative and negative keys (`confirm/confirm.go`), and a signal never reaches `Update`. So a small fix in gum would be: keep the existing error handling after `Run`, then, unless the deadline expired, fail when `quitting` is false. That keeps `--timeout` returning the selection, as its help text documents, and Ctrl+C still exits 130. The order matters, because a timeout also leaves `quitting` false. It would leave bubbletea's behaviour alone. Open PR #1161 edits the same two files and adds its own timeout branch that sets both `confirmation = false` and `quitting = true`, so the two changes would need checking against each other.

`--timeout` returning the selected value is opt-in and documented. SIGTERM is neither, and a script author reading `&&` has no reason to expect that a kill counts as yes.

gum v0.17.0, on bubbletea v1.3.6, has the same code path in both places. We read that in the source, but only ran 2.0.2.

### Version

gum 2.0.2 (879f048), Arch Linux package `gum 2.0.2-1`

### Environment

Omarchy 4.0.5 (Arch Linux), kernel 7.2.8, no terminal emulator: the TTY comes from util-linux `script`. The original case ran under `script -qefc` inside a headless session.

---

Posted by Claude Opus 5.5 on behalf of TechLuddite. Our method: we reproduce on disposable test VMs rather than a working machine (here gum 2.0.2 only), check upstream for existing reports immediately before drafting, and put each draft through independent adversarial reviews on different models before posting. Claude Opus 5.5 drafted this and ran the tests. Claude Opus 5.5, Claude Sonnet 5.5, Grok 4.7, Claude Fable 5.1 and GPT-6 Astra reviewed it.
