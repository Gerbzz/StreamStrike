# Windows CLI evidence, 2026-10-15

- [Successful hosted run](https://github.com/Gerbzz/StreamStrike/actions/runs/38704970118) on a standard Windows runner.
- Exact branch source commit: `06018bd1b8d97974ccbe17b5d216d601d99b9542`.
- `cargo test --locked`: 2 passed, 0 failed. `cargo build --locked --bin streamstrike` passed.
- The workflow created a synthetic `.streamstrike` project, then recorded the real CLI output in [windows-cli-transcript.txt](windows-cli-transcript.txt). Lines starting `PS>` identify commands supplied by the workflow; the remaining lines are output from the executable.
- [demo.streamstrike](demo.streamstrike) is the file saved by that run. Its parsed JSON matches the `show` result in the transcript.
- The `primary` display selector and `default` microphone selector are text values. No devices were opened and no media was recorded.
- This evidence shows a source-only CLI, not a native UI screenshot, live preview, recorder, or streaming application.

SHA-256 of the downloaded files:

```text
windows-cli-transcript.txt  167B4F7096CE20ED4256359D1F29000FB48B159944D043CD45B7572F0EBEF31B
demo.streamstrike           89285E4E58896B0A2504046C851C1DED4B24EE319B5B7A03B7C453D276D3565E
```
