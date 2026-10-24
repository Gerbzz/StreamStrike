> Historical checkpoint: the custom GUI direction below is superseded by the
> [original OBS foundation and preservation cutover](../OBS_CUTOVER.md). Existing
> capture artifacts describe their old source, not the current application.

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

## Native Linux editor evidence, 2026-10-23

- [Successful native workflow 40016933156](https://github.com/Gerbzz/StreamStrike/actions/runs/40016933156), Linux job `120632580278` and artifact `12528878338`.
- [Unmodified native editor PNG](streamstrike-editor-linux-20261023.png), 1160×740 RGBA. SHA-256 `1c5a8c5951cea2bac22bd326e03982cc3208be50c73b0e1ec455f63b57115f38`.
- The actual checkout was GitHub's synthetic merge `bf45cd970611a506f37e76b6f7999eb2dd1cda2c`, not the PR head. Its tree `b1c45076f3c747efd833af9d2b5ff314540ba551` exactly matches reviewed logo/source head `f17937c350f57ccd9abfc886d6678628ae9f9cad`.
- The real WGPU editor ran under Ubuntu 24.04/Xvfb with software Vulkan/Lavapipe and loaded `demo.streamstrike`. Fourteen core/editor tests and the separate app-produced PNG detail gate passed.
- [Machine-readable capture provenance](streamstrike-editor-linux-20261023.provenance.json) records hashes, exact command, source, artifact and limits.
- This is honest project-setup GUI evidence, not a recording/streaming or OBS rewrite claim. No physical devices were opened; there is no live preview, recording or streaming. Runtime/packaged product-logo integration was not part of this work.
- The Windows job passed its build/tests but produced no native screenshot: `Wgpu(NoSuitableAdapterFound)`, process exit 1. Windows native GUI acceptance is not claimed.
