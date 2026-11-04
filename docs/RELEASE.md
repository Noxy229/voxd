# Earlier release verification — 2026-11-04

The model/Qt measurements below describe the earlier implementation before the
dictionary-only default. The newer dictionary defaults and installers
are documented in [INSTALLERS.md](INSTALLERS.md); Qwen is no longer the default.

Implemented and locally checked; not a blanket certification for every desktop.

## Checks completed

- 23 regression tests pass, including Qt offscreen setup/download tests.
- Ruff checks pass. Wheel and source archive build successfully.
- Actual Parakeet INT8 weights load locally (2.21 s in one run) and return an
  empty transcript for one second of silence. This is not an accuracy benchmark.
- Actual Qwen3 1.7B Q4_K_M weights downloaded and loaded with local llama-server.
  File size: 1107 MB decimal. One editor startup measured 0.61 s. These timings
  are single-run observations on this machine, not universal promises.
- Two German self-corrections succeeded in the final smoke run (0.69 s and 0.56 s).
  A request with a requested line break needed the deterministic fallback
  (0.63 s): the editor removed the line break, and the new guard rejected it.
  The earlier long prompt also lost the request's question form. The shorter
  prompt plus question/line-break guards address these observed cases, not
  arbitrary semantic changes. Compact-model quality remains a known tradeoff.
- The editor process remained loaded after requests and was terminated on close.
- Real Qt Wayland/KDE smoke test exposed focus theft with an ordinary tool window.
  The Plasma Wayland path now uses tray status; its overlay is suppressed. The
  corrected smoke test verifies no overlay keyboard focus. Native layer-shell
  support has not been implemented.

## Privacy review

A local pattern scan inspected 51 historical Git blobs and the working tree for
private-key headers, common credential formats, personal home-directory paths,
and (in historical text blobs) email addresses. No matching sensitive file
content was found. Build artifacts were checked to exclude local environments,
recordings and credential files. This limited pattern scan is not a complete
secret or binary-content audit.

Normal completion logs and IPC status no longer contain dictated text. Local
recordings, keys, environment files and logs are ignored by Git. The generated
product illustrations come from the offscreen drawing script, not desktop
captures. README claims and install commands were corrected; personal repository
links were removed from the downloader and installation instructions. The MIT
copyright notice remains required attribution, including its public handle.

Before the first public release, reachable author/committer metadata was
normalized to the project's public GitHub noreply identity. A private local
Git bundle retains the pre-public history outside the repository. Source and
reachable historical text were scanned for credentials, private-key markers,
known private identity addresses and personal paths; example test addresses
and the MIT copyright attribution are intentional.

The release contains Linux and Windows terminal installers plus SHA256SUMS.
The checksum guards detect damaged/mismatched assets; they are not code signing.
This review does not prove that every possible secret pattern is absent.
GitHub may retain old unreferenced objects after a history update; the audit
covers the refs and assets published for this release.

## Remaining acceptance work

On the target Plasma session, assign the generated application shortcuts in KDE
System Settings, configure ydotoold, then dictate into a native Wayland editor,
a browser and an XWayland application. Confirm focus, umlauts, multiline paste,
manual clipboard recovery and behavior with Klipper enabled. Test real German
speech with a representative set of names, corrections, pauses and background
noise; measure transcription errors, semantic edit errors, warm latency and
steady-state RAM. No microphone recording or insertion into existing windows was
performed during automated verification.

Windows hardware validation, a native Plasma layer-shell overlay, clipboard
MIME preservation, cryptographically pinned model downloads and broad desktop
acceptance remain open. The first public release publishes the reviewed source and installers.
