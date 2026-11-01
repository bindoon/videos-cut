# Project rules

Start at `README.md` and `docs/README.md`; usage lives in `docs/usage.md`, AI operation in `docs/ai-guide.md`, and current architecture in `docs/architecture.md`. Actual validation history lives in `docs/verification.md`.

- A failing test means suspect the implementation first. Do not weaken, skip, or delete an acceptance assertion merely to make a change pass; changing the intended requirement needs the user's agreement.
- Download tests require the optional backend: use `uv sync --extra download --extra asr` before the complete suite. The checks in `tests/test_downloads.py` use actual local HTTP and FFmpeg; keep network platform smoke checks separate from the deterministic suite.
- A track returned in yt-dlp's `subtitles` field is not proof of human authorship: TikTok also exposes automatic captions there. Preserve platform provenance and use `generation=unspecified` when the provider does not establish how a track was made.
- `transcribe` is independent: `no_speech` is a valid standalone result. Keep required-word and speech-coverage rejection in editing consumers; do not move those gates into the shared ASR implementation. ASR timestamps are not Qwen forced-alignment records.
- When changing ASR timestamp ownership or cache-payload semantics, update `SCHEMA` in `videocut/transcription.py`; otherwise existing valid caches can silently preserve the previous algorithm's results even when fresh-fixture tests pass.
- For standalone FFmpeg operations, use the project skill at `.agents/skills/ffmpeg-skill/SKILL.md` through `videocut ffmpeg`; integration boundaries live in `docs/ffmpeg-tools.md`. Its `verified`/`check` results do not replace the project's Qwen alignment or `sync.py` acceptance, and its optional transcription does not use our ASR cache/provenance contract.
- Keep platform-specific content decisions in scene skills/templates (for example `.agents/skills/xiaohongshu-quotes/`); reusable frame, image, cache and validation mechanics belong in generic tools. Do not bake Xiaohongshu topic/copy/layout rules into `images`; see `docs/capabilities.md` and `docs/image-tools.md`.
