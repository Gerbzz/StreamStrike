<p align="center">
  <a href="https://prowebdevsolutions.com"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/branding/PWDS-logo-orange.svg">
    <img src="assets/branding/PWDS-logo.png" alt="PWDS company logo" width="120">
  </picture></a>
</p>
<p align="center"><strong>Published by PWDS</strong></p>

<h1 align="center">StreamStrike</h1>

**Set the scene for what comes next.**

StreamStrike is a local scene and source project editor for a future recorder and streamer. Create a project, arrange scenes, describe display and audio sources, and save the setup for later work.

## Current status

The native editor work in [PR #2](https://github.com/Gerbzz/StreamStrike/pull/2) and [PR #3](https://github.com/Gerbzz/StreamStrike/pull/3) merged on 18 October 2026. Main includes a native Rust scene/source project editor alongside the CLI. It opens, creates, edits, validates, and saves real `.streamstrike` projects. Source selectors are descriptions only: no display or audio device is opened. There is no live preview, recording, replay buffer, mixer signal, or streaming.

## Features

- Create and select scenes in a local project.
- Describe display, window, microphone, and desktop-audio sources.
- Store mute and gain settings for audio sources.

## Build and install

Source builds require Rust with support for the manifest's 2024 edition. The source defines CLI and native editor targets; no installer is included.

```text
cargo build --locked --bin streamstrike --bin streamstrike-editor
```

### Run the editor

On a Windows desktop with Rust installed, run `cargo run --locked --bin streamstrike-editor`. Use New, Open, Save, and Save as to manage `.streamstrike` files; the Scenes and Sources panes edit the same validated project model as the CLI. `--open PATH.streamstrike` opens a project at launch. The toolbar supports Ctrl+N, Ctrl+O, and Ctrl+S. Unsaved project changes prompt before New, Open, or Close. A hosted native screenshot attempt uses `--capture OUTPUT.png` with the included synthetic project; it does not exercise physical devices.

## Validation status

### Verified Windows CLI run

The [Windows run on the exact source commit](https://github.com/Gerbzz/StreamStrike/actions/runs/38704970118) passed two Rust tests, built the CLI, and executed these commands against a synthetic local project:

```text
streamstrike new demo.streamstrike
streamstrike add-scene demo.streamstrike Game
streamstrike select-scene demo.streamstrike 2
streamstrike add-source demo.streamstrike 2 Monitor display primary
streamstrike add-source demo.streamstrike 2 Voice microphone default
streamstrike set-audio demo.streamstrike 4 false -6
streamstrike show demo.streamstrike
```

The [actual CLI transcript](docs/evidence/windows-cli-transcript.txt), [resulting project](docs/evidence/demo.streamstrike), and [capture provenance](docs/evidence/README.md) are retained in this repository. For example, the executable reported `added source ID 4; selector is stored but not opened` and `stored audio settings for source ID 4; no audio device is opened`. This is command output from the earlier CLI checkpoint. The native editor has a separate [hosted build and capture workflow](.github/workflows/editor-preview.yml). No GUI screenshot is committed here, and the retained CLI evidence does not establish desktop GUI acceptance.

`new` refuses an existing path. Edits validate the full project and use a staging file and old-project backup. If a save is interrupted, the program leaves sidecars for inspection and refuses to overwrite them. The format is limited to 1 MiB. Nothing in this CLI records audio/video or contacts a service.

## Next functional slice

1. Review and test the native editor on a real desktop, including keyboard focus, dialogs, and save recovery.
2. Pin a verified engine/API combination and document license, notice, runtime, and platform obligations. Resolve real display, window, and audio devices through that engine and report unavailable devices clearly.
3. Show a real preview and meters, then start and stop bounded local recording. Verify the output and test device loss, disk-full behavior, and finalization.
4. Add replay buffering and streaming only after recording is stable.

See [DECISIONS.md](docs/DECISIONS.md) for options and dependency status.

## Development direction

The native editor is a project setup tool; a media engine is the next milestone. `libobs` is a researched candidate, not a chosen or bundled dependency. The interface uses the StreamStrike name and shows the existing approved PWDS mark in About; a distinct StreamStrike icon remains undecided. See [DECISIONS.md](docs/DECISIONS.md).

## Credits and licenses

No first-party source license grant is made by this checkpoint; choose an explicit project license before distribution. Dependency notices and license compatibility remain distribution gates in [DECISIONS.md](docs/DECISIONS.md). No OBS Project affiliation is claimed.

### PWDS publisher artwork

The company mark in this masthead is the existing [official PWDS logo](https://github.com/Gerbzz/PWDS-Website/blob/main/public/prowebdevsolutions-logo.png), with the [official orange display asset](https://prowebdevsolutions.com/images/prowebdevsolutions-logo-orange.svg) for dark backgrounds. This is PWDS publisher artwork, not a StreamStrike app logo.
