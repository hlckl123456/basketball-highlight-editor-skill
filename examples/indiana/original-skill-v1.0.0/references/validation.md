# Validation scope and limits

Test date: 2026-10-27, America/Los_Angeles. This is a working assisted workflow, not a validated autonomous basketball-player recognition model.

## Public real-video smoke test

- Video: [Indiana Legends Versus Indiana Lyons, 20240224 183141 (165) (165).webm](https://commons.wikimedia.org/wiki/File:Indiana_Legends_Versus_Indiana_Lyons,_20240224_183141_(165)_(165).webm), 16.3 seconds, 1920×1080, 30fps.
- Creator: Koavf / Justin Anthony Knapp; own work, CC0 1.0 on the file page. Source revision 1015581460. The task stores the exact byte count, SHA256, source/download/license URLs and restrictions in its rights manifest. This material is for local testing, not represented as the user's footage or publishing clearance.
- Reused already-downloaded BHE 0.1.12 DMG runtime; no software installed and no video uploaded to a third-party app. Public source CLI, CPU ONNX Runtime, source ROI `[0,0,700,700]`, 15 samples/second. Default before/after handles: 3 and 2 seconds.
- Full-frame first run at 10fps returned 1 dubious candidate around 6.55s. Adjusting ROI returned 4 crossings at 2.63, 4.57, 11.57 and 12.43s. Early crossings are false/dubious and later crossings overlap. A moving-camera clip is a difficult BHE input. Do not report these 4 as 4 made baskets.
- Packaged OpenCV had no HOG. Fallback color-region extraction produced 639 proposals over 16 sampled frames, with spectator/sign false positives and missed/partial player crops. OCR suggestions include wrong/partial digits. No automatic identity assignments were accepted from these hints.
- The user chose the purple-uniform player numbered 2. Codex recorded frame evidence, distinguishing white short sleeves, bare knees and white-gray shoes from same-color teammates. `c0001` and `c0003` are clear target-presence candidates; `c0002` and `c0004` remain manual-review items for overlap or ambiguity. `c0003` is off-ball defense while a white-uniform player shoots; it is not labeled as the selected player's score.
- A 9.5-second full-body sample produced 17 short-range optical-flow proposals spanning 8.9 to 12.3 seconds. They remain unverified proposals. The sample command does not use OCR and never promotes identity automatically. This validates sample/continuity mechanics, not recognition performance on a real unnumbered game.
- An additional `features --no-ocr` smoke test over 3 coverage windows produced 234 color proposals, zero number hints and zero automatic identity assignments. This tests explicitly ignoring numbers on the same licensed source; it does not replace a genuinely unnumbered-game evaluation.
- The user actually confirmed the sample and kept `c0001`/`c0003`, rejecting `c0002`/`c0004`. The live project reached revision 10, `awaiting_edit_prompt`, with a confirmed EDL and no versions or merged reel. Test-operator confirmation and later version rendering were exercised on a separate project copy, yielding 6.03s and 9.635352s landscape MP4s. The nominal short EDL was 6 seconds; container duration includes frame/audio rounding. All 4 rough clips and 2 test renders decoded without FFmpeg errors.
- A repeated CPU run produced exactly the same event times `[2.63,4.57,11.57,12.43]` with identical source/model/script hashes. The 14 behavioral regression tests passed. Test logs and machine-readable evidence accompany the task outputs.

## Regression tests

`tests/test_workflow.py` exercises source integrity, out-of-bounds ranges, color-only identity rejection, saved-sample requirements, uncertainty routing, explicit reviewer attribution, incomplete/stale/wrong-player review rejection, no render on confirmation, rejection of excluded clips in later versions, and two independent rendered versions from silent source. The concrete run log accompanies the task's outputs; run the suite again after code changes.

## What has not been established

No measured full-game precision/recall, tracking identity-switch rate or unnumbered-player identification accuracy. No guarantee of all possessions, assists, steals or defensive involvement. No validated face recognition, person re-identification embedding model, smart portrait reframing, soundtrack/caption system, or native CapCut/Jianying project integration. A short clip with one selected player and manual evidence review cannot substantiate those claims.

For similar uniforms without unique visible clothing, ask for additional confirmed samples and keep unresolved clips uncertain. If clothing remains indistinguishable, manual review is required. Never make an unsupported person match simply to fill the high-confidence group.
