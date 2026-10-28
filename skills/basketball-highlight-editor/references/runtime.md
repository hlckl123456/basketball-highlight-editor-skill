# Local runtime and BHE boundary

The tested runtime is from the user's already downloaded `BHE-macos-arm64-v0.1.12-adhoc.dmg`, read-only mounted at `/Volumes/BHE`. No application was installed. On this machine, the first startup was slow; subsequent CLI runs worked. Do not strip quarantine or change security settings to speed it up.

```sh
BHE_RUNTIME="/Volumes/BHE/BHE.app/Contents/Resources/runtime"
BHE_PY="$BHE_RUNTIME/python/bin/python3.11"
"$BHE_PY" /absolute/skill/scripts/highlight.py doctor
```

After a restart, the mount may be absent. Reuse an installed app if one exists or read-only mount the existing disk image with `hdiutil attach -readonly -nobrowse -noautoopen <DMG>` within the host's permissions. Explain failures. Never interpret a missing mount as permission to download or install another runtime.

Runtime prerequisites:

- Base: Python 3.10+, FFmpeg and FFprobe on PATH. No pip dependencies for state, cut, review or version commands.
- Features/sample: NumPy and OpenCV; tested with the BHE Python 3.11.16, NumPy 2.4.6 and OpenCV 5.0.0. Tesseract is optional for number hints. The packaged OpenCV lacks HOG; tested fallback is color-region proposals, with many signs and spectators among proposals.
- BHE detection: public `scripts/scan_video.py`, `scripts/generate_candidates.py`, `src/basketball_highlight`, model and their existing dependencies. The wrapper records file hashes in each project. It disables Ultralytics auto-install and directs config into the project. CPU is the reproducible default. A requested device does not prove acceleration; the raw log records the actual provider.

Public source references:

- [BHE repository](https://github.com/fly7632785/basketball-highlight-editor)
- [public scan CLI](https://github.com/fly7632785/basketball-highlight-editor/blob/v0.1.12/scripts/scan_video.py)
- [public candidate CLI](https://github.com/fly7632785/basketball-highlight-editor/blob/v0.1.12/scripts/generate_candidates.py)
- [public engine protocol](https://github.com/fly7632785/basketball-highlight-editor/blob/main/docs/architecture/ENGINE_PROTOCOL_V1.md)

This skill invokes public source CLI scripts and reads their JSON output. It does not automate BHE GUI controls, private IPC or its SQLite internals. Candidate schema in this tested version uses `candidates[].time`. Future versions may differ; inspect public source and test a new adapter instead of guessing fields. Missing model/dependencies, no hoop detections and timeouts are failures with a diagnostic file, not successful empty results. A valid zero-candidate run is allowed, but cannot proceed to player analysis; check ROI or explicitly use coverage windows.

Source code and model licensing are separate. This skill does not redistribute BHE models or runtime. The existing third-party runtime retains its own license obligations. The test video has a separately recorded CC0 source; no BHE example video was assumed licensed for reuse.
