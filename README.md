# StreamStrike

StreamStrike is the beginning of a free, local recording and streaming application in the Strike suite. This checkpoint is a **source-only Rust project core and CLI**, not a screen recorder. It can create a versioned project, add and select scenes, add display/window/microphone/desktop-audio source descriptions, store mute and gain for audio sources, and reload the project. Source selectors are strings for a future engine to resolve; they do not open devices. There is no live preview, capture, mixer signal, recording, replay buffer, or streaming yet.

Part of the Strike suite by PWDS.

The future native app should show the StreamStrike name and its own approved logo on launch, with a separate “by PWDS” publisher mark. This checkpoint has no native launch UI, splash screen, or approved logo asset.

The first native milestone is Windows-first, with Linux and macOS planned. The proposed integration is a Rust application shell and project logic over an isolated native media engine adapter. `libobs` is the current leading engine candidate based on the linked research in [DECISIONS.md](docs/DECISIONS.md); it is C/C++, so such an app would **not** be pure Rust. No engine is chosen, downloaded, linked, or bundled by this checkpoint.

## Source-level CLI contract

When dependencies can be built within the disk budget, the commands are:

```text
streamstrike new demo.streamstrike
streamstrike add-scene demo.streamstrike Game
streamstrike select-scene demo.streamstrike 2
streamstrike add-source demo.streamstrike 2 Monitor display primary
streamstrike add-source demo.streamstrike 2 Voice microphone default
streamstrike set-audio demo.streamstrike 4 false -6
streamstrike show demo.streamstrike
```

`new` refuses an existing path. Edits validate the full project and use a staging file and old-project backup. If a save is interrupted, the program leaves sidecars for inspection and refuses to overwrite them. The format is limited to 1 MiB. Nothing in this CLI records audio/video or contacts a service.

## Next functional slice

1. Pin a verified engine/API combination and document all license, notice, runtime, and platform obligations. Keep the engine behind a narrow Rust adapter with explicit lifecycle and error mapping.
2. Build a native scene/source editor that drives the project model. Resolve a single display or window and microphone/desktop audio devices through the engine. Show a real preview and real meters, or show an actionable unsupported/device error.
3. Start and stop bounded local H.264 recording, verify the resulting file, and save/reload the project. Test device loss, low disk space, and recording finalization before claiming recording works.
4. Add replay buffering and then streaming after recording is stable. Design output ownership so a failed stream cannot silently interrupt local recording.

See [DECISIONS.md](docs/DECISIONS.md) for options and dependency status. No license is granted for new StreamStrike source by this checkpoint; choose an explicit project license before distribution. No OBS Project affiliation is claimed.
