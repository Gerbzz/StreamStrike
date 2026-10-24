> Historical checkpoint: the custom GUI direction below is superseded by the
> [original OBS foundation and preservation cutover](OBS_CUTOVER.md). Existing
> capture artifacts describe their old source, not the current application.

# CLI evidence workflow

The [Windows CLI evidence workflow](../.github/workflows/cli-evidence.yml)
builds this exact branch on a standard GitHub-hosted Windows runner. It runs
the current Rust CLI against a new synthetic `.streamstrike` project, records
each command and its actual output, then uploads the transcript, project, and
source commit as a short-lived artifact.

The selector names `primary` and `default` are stored project text. The CLI
does not open a display or microphone. This artifact can support a source/CLI
status page after inspection; it is **not** a screenshot of a native editor,
recorder, preview, or streamer. No such UI exists in this checkpoint.
