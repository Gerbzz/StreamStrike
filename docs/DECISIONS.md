> Historical checkpoint: the custom GUI direction below is superseded by the
> [original OBS foundation and preservation cutover](OBS_CUTOVER.md). Existing
> capture artifacts describe their old source, not the current application.

# StreamStrike foundation decisions and open gates

## Current choice: project core only

This checkpoint adds only original Rust scene/source project code plus pinned registry references to `serde 1.0.228` and `serde_json 1.0.149`. It copies no source, assets, marks, or notices from another app. The dependencies are not vendored; their full transitive notice inventory and compatibility must be checked before distribution. The new project source has no license grant yet.

The project model gives each scene and source a stable ID, validates names and source selectors, tracks the active scene, and stores audio mute/gain. The selectors are unresolved references; storing one is not proof that a display, window, or device exists. Engine state must never be inferred from project JSON alone.

## Candidate media engines

| Option | Fit | Decision gate |
| --- | --- | --- |
| [OBS Studio/libobs](https://github.com/obsproject/obs-studio/releases/tag/32.2.2) via a Rust adapter | Mature scene, source, mixer, capture, output, recording, and replay concepts. OBS Studio/libobs is C/C++, not Rust, and OBS Studio is GPL-2.0-or-later. | Pin compatible native binaries/source and bindings; verify Windows behavior, runtime packaging, GPL obligations, and later Linux/macOS support. |
| [libobs-rs](https://github.com/libobs-rs/libobs-rs) | Community Rust wrapper with recording/RTMP/replay and scene/mixer/output APIs. | API is marked unstable; Windows/Linux have been exercised, while macOS support is reported incomplete. Verify exact revision, OBS version, and lifecycle before adopting. Wrapper reports GPL-3.0 licensing; confirm distribution implications. |
| GStreamer with Rust bindings | Alternate native media pipeline if libobs integration fails. | Would need substantial scene composition, capture, replay, and output work. Verify platform plugins/codecs, licensing, and any existing suite usage before choosing it. |

[OBS frontend documentation](https://docs.obsproject.com/frontends) is a reference for native frontend integration, not evidence that a compatible donor is already present.

The planned adapter owns all native handles and exposes typed operations for initialization, source/device enumeration, scene activation, source attachment/removal, preview frames, audio levels, local recording start/stop, replay-buffer save, and shutdown. The Rust project model remains independent of those handles. Each native call must report a result rather than implying success from stored project state. The integration must define a thread boundary for libobs callbacks, map device loss and output errors into user-visible state, drain/finalize recording on stop, and release outputs and sources before engine shutdown. Those contracts are design gates, not implemented interfaces in this checkpoint.

## Local suite inspection

- AudioStrike's local Rust preview (`2026-10-10/task-7/audiostrike`) has scene-adjacent audio patterns: device output via CPAL, a bounded ring, mixer behavior, a project file, and attribution notes. Its recording writer accepts caller-supplied samples; the documented preview has no recording UI or device input path. Its code has **not** been copied.
- FilmCraft source (`2026-10-10/task-5/filmcraft-source`) has Rust audio/media work, but its `AGENTS.md` prohibits copying GPL code into that donor. Its source has **not** been copied or modified.
- PhotoCraft's `screen_color.rs` uses one-shot screen snapshots for a color picker. It does not supply continuous recording, timing, encoder, or replay functionality. Its code has **not** been copied.

These are patterns to inspect later, not an assumption that their components can be transplanted into an OBS-based app. Preserve each project's licenses, notices, and local data.

## Branding and release gates

The user requested removing OBS from the app name. **StreamStrike** is the provisional local working name; PWDS is the Strike suite publisher, not part of the app name. Trademark availability has not been checked. The [OBS Project IP policy](https://obsproject.com/forum/threads/forum-resource-and-ip-policy.178569/) remains relevant if libobs is used, but OBS appears here only as a technical upstream reference. No affiliation is claimed. A final name and marks review remain release gates.

Launch identity requirement: the native app must visibly present its own StreamStrike name and approved logo alongside a distinct “by PWDS” publisher mark. An original or properly licensed logo and its attribution must be approved before packaging. The current CLI has no graphical launch experience or logo, so this remains unimplemented.

Before any public release: decide the project's license; enumerate all native and Rust dependency obligations; preserve donor notices; verify codec and capture permissions on each platform; test live preview, device/audio behavior, bounded local recording, replay recovery, and disk-full handling. Streaming credentials and live streaming are outside this checkpoint.
