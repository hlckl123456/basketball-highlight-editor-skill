# Commands and data

Use absolute paths in actual calls. Examples below use task-specific shell variables:

```sh
SKILL_DIR="/absolute/path/basketball-highlight-editor"
PROJECT_DIR="/absolute/path/my-game"
BHE_RUNTIME="/Volumes/BHE/BHE.app/Contents/Resources/runtime"
BHE_PY="$BHE_RUNTIME/python/bin/python3.11"
python3 "$SKILL_DIR/scripts/highlight.py" init "$PROJECT_DIR" --video /absolute/game.mp4 --rights /absolute/rights.json
python3 "$SKILL_DIR/scripts/highlight.py" detect "$PROJECT_DIR" --backend bhe --runtime "$BHE_RUNTIME" --roi 0 0 700 700 --fps 15 --device cpu
"$BHE_PY" "$SKILL_DIR/scripts/highlight.py" features "$PROJECT_DIR" --interval 1.5
```

ROI values above are from the test video and must be adapted to the real source. They are source-pixel XYXY, with a visible hoop and surrounding ball flight. Full-frame moving-camera detection returned a false candidate in the smoke test. Even the adjusted ROI produced false/duplicate detections.

`rights.json` requires `source_url`, `license`, `creator`, `processing_basis` and `restrictions`. For the user's own game, record that the user supplied and requested local processing; do not assert public publishing rights. Test downloads need a verifiable source, applicable license, creator and restrictions. `init` references the local source and hashes it; it does not copy, upload or alter it.

Optional portable input:

```json
{"provenance":"User-exported BHE ranges; original source timebase", "candidates":[{"start":12.0,"end":18.0,"reason":"BHE candidate"}]}
```

Use `import-candidates PROJECT --file manifest.json` for these ranges. For separately exported clips without source offsets, make separate projects or request their time mappings; do not invent original timestamps. Add a missed play with `add PROJECT --start 20 --end 28 --reason 'manual assist candidate'`.

## Unnumbered-player calibration

For unnumbered footage, run `features PROJECT --no-ocr` under the BHE Python to skip number extraction and unnecessary OCR work. It still saves clothing color proposals and original frames.

Show the original frame and ask the user to point to a person before calling:

```sh
"$BHE_PY" "$SKILL_DIR/scripts/highlight.py" sample "$PROJECT_DIR" --player personA --time 9.5 --bbox 1355 465 1660 1075 --description 'purple shorts, white short sleeves, bare knees, white-gray shoes' --confirmed-by 'actual user message or local sample review reference' --reviewer-kind user
```

The numeric values are examples, not a reusable person detector. `sample` saves the crop and forward/backward sparse optical flow proposals without OCR. Proposals never assign identity. Inspect track boxes against original frames and require visible stable-feature agreement before `confirmed_sample_match`. Use a new sample after a camera cut or appearance change; retain uncertainty when teammates cannot be distinguished. Tests use `test_operator` instead of `user`. No calibrated recognition probability is produced.

If a sample was initially positioned by a test operator and the user later confirms that exact displayed crop, record their actual reply with `confirm-sample PROJECT --sample-id s001 --authorization-reference 'actual reply reference'`. This records the transition without pretending the original sample was user-confirmed.

## Evidence annotation, then selection

```json
{
  "reviewer":{"kind":"agent_visual_review","name":"Codex; checked original frames"},
  "players":[{"id":"personA","description":"purple uniform, white short sleeves, bare knees, white-gray shoes","reference":"samples/s001.jpg"}],
  "assignments":[
    {"candidate_id":"c0001","player_id":"personA","certainty":"high","reason":"visible stable clothing matches the user-confirmed sample","role":"off_ball_defense","evidence":[{"kind":"confirmed_sample_match","sample_id":"s001","time":10.1,"detail":"white sleeves, bare knees and gray-white shoes match; no lookalike at this time"}],"labels":["defense"]},
    {"candidate_id":"c0002","player_id":null,"certainty":"uncertain","reason":"occluded; same-color teammate nearby","evidence":[]}
  ]
}
```

`number_visible` is the other high-confidence evidence kind. Provide the verified number and frame timestamp; raw OCR does not count as verification. A sample match without a saved sample for that player is rejected. `needs_review: true` routes an otherwise clear match to the uncertain review group for duplicate or role questions. `other` explicitly excludes a candidate; `high` assigned to another player also goes to `other`. Missing assignments stay uncertain.

```sh
python3 "$SKILL_DIR/scripts/highlight.py" annotate "$PROJECT_DIR" --file /absolute/annotations.json
python3 "$SKILL_DIR/scripts/highlight.py" select "$PROJECT_DIR" --player personA --selected-by 'actual user answer reference'
python3 "$SKILL_DIR/scripts/highlight.py" rough "$PROJECT_DIR"
python3 "$SKILL_DIR/scripts/highlight.py" status "$PROJECT_DIR"
```

The HTML form downloads decisions; it has no server and sends nothing. Alternatively, translate the user's keep/reject reply to this JSON using the current project revision:

```json
{"project_revision":6,"player_id":"personA","reviewer_kind":"user","reviewer":"user","authorization_reference":"actual keep/reject message reference","decisions":{"c0001":"keep","c0002":"reject"}}
```

```sh
python3 "$SKILL_DIR/scripts/highlight.py" confirm "$PROJECT_DIR" --file /absolute/decisions.json
```

The command rejects stale revision, wrong player and missing decisions. It saves an EDL and `awaiting_edit_prompt` without rendering. Rejected ranges remain in the project. The human may deliberately keep an uncertain clip; its original uncertainty remains in history.

## Later editing prompts

On a later user request, write a new spec:

```json
{"prompt":"Make a short landscape version from my confirmed clips, max 6 seconds, put the defense first", "clip_ids":["c0003","c0001"],"max_duration":6}
```

```sh
python3 "$SKILL_DIR/scripts/highlight.py" version "$PROJECT_DIR" --name short-defense --spec /absolute/version-spec.json --render
```

Without `--render`, this writes only an independent EDL. Each version has its own directory and stored prompt. Clip order follows `clip_ids`, duration is capped by trimming the last included clip, and rejected IDs are disallowed. The renderer normalizes landscape previews to 1280×720 at 30fps, preserves optional audio, and handles silent input. It does not make portrait crops, titles, music, slow motion or a native CapCut/Jianying project. Do not claim a generic natural-language editor is embedded in the CLI; Codex translates the user's prompt into supported, reviewable settings.

The duration cap controls EDL clip lengths. Muxed duration can differ slightly through frame and audio-packet rounding; the real 6-second smoke-test version probed as 6.03 seconds.

## Reopening and invalidation

Resume from `status PROJECT`; do not start a new project just to make another version. `source.path` must remain available with the same SHA256. If moved, use `relink PROJECT --video NEW_PATH`; this checks the same hash and records the change without invalidating the selection. There is no automatic search through personal files. `features` processes only new candidates by default; `--refresh` recomputes features and clears player profiles. Changes to candidates, annotations, samples or selection invalidate confirmation. Confirmed EDL files are snapshots; the current `project.json` state decides whether rendering is allowed. One writer per project is supported.
