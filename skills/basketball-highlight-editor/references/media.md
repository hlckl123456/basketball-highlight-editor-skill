# Media handling and repeatable tests

`init` checks a local movie with FFprobe and bounded first/tail frame decoding. Missing, empty, audio-only, invalid-duration, truncated, unsupported-rotation and unavailable-codec inputs give actionable error codes. This is a bounded integrity check, not proof that every packet in a two-hour recording is intact. A later corrupt range can still fail when processed; restore or explicitly re-encode that original instead of silently dropping it.

All EDL seconds are relative to the first video picture. FFmpeg extraction and rendering seek against that video timestamp origin, including containers whose audio priming starts earlier. Autorotation determines displayed coordinates. Samples, clothing frames and rendered clips use the same presentation-time convention; VFR does not use frame-number division to approximate seeks.

The renderer emits 1280×720 H.264 at the source nominal rational rate. VFR is resampled to CFR using source PTS. Portrait input is padded, not automatically reframed. Optional audio becomes 48kHz stereo AAC; a short track is padded with silence. Silent input stays silent. Version EDLs contain exact allocated frame counts; cumulative rounding avoids drift across many clips. Rough media is reused only when its hash, source hash, render schema, time range and frame quota all match.

## Detection cache

`detect` defaults to a content cache beside the project in `.basketball-cache/`. The key includes video SHA256, all detector parameters, adapter/media code, FFmpeg version and applicable BHE model/scripts/src hashes. `--backend manifest --manifest ranges.json` is an explicit cached import of existing candidate ranges, not fresh shot detection.

Use `--cache-dir PATH`, `--no-cache` or `--refresh-cache` as needed. Cache hits skip external inference and restore raw detection JSON. `detection/cache-status.json` records hit/miss and the key separately from reproducible project state. Corrupt payloads fail closed with instructions to remove/recompute the entry. Source hashes are memoized only within a process against file identity, size and modification/change timestamps; a new process rehashes the source.

The cache belongs to the local workflow. It is not a security boundary against an attacker who can replace both cached data and its checksum. Python dependency or decoder changes beyond recorded versions should use `--refresh-cache` for a fresh comparison.

## Test-only reproducibility

`init --reproducible --epoch 946684800` enables an explicit fixed logical test clock and canonical JSON key ordering. The same source, rights, candidate manifest, parameters, software environment and test decisions produce byte-identical project and EDL JSON. Ordinary user projects retain real operation times.

Fixed-clock projects require `test_operator` for samples, annotations and clip confirmations; they reject user/agent attribution and `confirm-sample`. Never use this switch to manufacture a human timestamp. It is unrelated to human-confirmed, hash-locked evaluation facts.

The repository's `robustness/` harness creates ignored video variants and runs full state transitions twice. Its frame-clock assertions inspect source PTS and rendered picture content. The matrix and benchmark are engineering tests, not new shot or player accuracy labels.
