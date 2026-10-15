# StreamStrike

<p align="center">
  <a href="https://prowebdevsolutions.com"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/branding/PWDS-logo-orange.svg">
    <img src="assets/branding/PWDS-logo.png" alt="PWDS company logo" width="120">
  </picture></a>
</p>

**Set the scene for what comes next.**

StreamStrike is laying out the projects behind a future recorder and streamer. Create a project, arrange scenes, describe display and audio sources, and save the setup for later work.

## Highlights

- Create and select scenes in a local project.
- Describe display, window, microphone, and desktop-audio sources.
- Store mute and gain settings for audio sources.

## Current status

Source-only Rust project core and CLI. Source descriptions do not open devices, and there is no preview, recording, replay buffer, mixer signal, or streaming yet. A media engine and native editor remain future work.

## Verified Windows CLI run

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

The [actual CLI transcript](docs/evidence/windows-cli-transcript.txt), [resulting project](docs/evidence/demo.streamstrike), and [capture provenance](docs/evidence/README.md) are retained in this repository. For example, the executable reported `added source ID 4; selector is stored but not opened` and `stored audio settings for source ID 4; no audio device is opened`. This is command output, not a native app screenshot; there is no native editor to capture yet.

`new` refuses an existing path. Edits validate the full project and use a staging file and old-project backup. If a save is interrupted, the program leaves sidecars for inspection and refuses to overwrite them. The format is limited to 1 MiB. Nothing in this CLI records audio/video or contacts a service.

## Next functional slice

1. Pin a verified engine/API combination and document all license, notice, runtime, and platform obligations. Keep the engine behind a narrow Rust adapter with explicit lifecycle and error mapping.
2. Build a native scene/source editor that drives the project model. Resolve a single display or window and microphone/desktop audio devices through the engine. Show a real preview and real meters, or show an actionable unsupported/device error.
3. Start and stop bounded local H.264 recording, verify the resulting file, and save/reload the project. Test device loss, low disk space, and recording finalization before claiming recording works.
4. Add replay buffering and then streaming after recording is stable. Design output ownership so a failed stream cannot silently interrupt local recording.

See [DECISIONS.md](docs/DECISIONS.md) for options and dependency status. No license is granted for new StreamStrike source by this checkpoint; choose an explicit project license before distribution. No OBS Project affiliation is claimed.

## Development direction

The next milestone is a Windows native scene/source editor connected to a verified media engine. `libobs` is a researched candidate, not a chosen or bundled dependency; a future integration would include C/C++ code and require a license and runtime audit. The current checkpoint has no native launch UI or approved StreamStrike logo asset. See [DECISIONS.md](docs/DECISIONS.md). No first-party source license grant is made by this checkpoint.

## PWDS brand artwork

The company mark in this masthead is the existing [official PWDS logo](https://github.com/Gerbzz/PWDS-Website/blob/main/public/prowebdevsolutions-logo.png), with the [official orange display asset](https://prowebdevsolutions.com/images/prowebdevsolutions-logo-orange.svg) for dark backgrounds. Any app logo above it remains the original Strike suite artwork.
