# Acquisition Methods

## Bilibili

- Read video metadata with `x/web-interface/view` to get title, owner, publish time, duration, description, and CID.
- Read official subtitles with `x/player/v2`; save subtitle JSON and plain text when available.
- If official subtitles are missing, try `bccdl`; if that fails, download audio with `yt-dlp` or playurl API and transcribe locally.
- Descriptions are metadata only. Mark content complete only when subtitles or full audio transcript exists.

## Podcast

- Extract Apple Podcast episode id from the `i=` query parameter.
- Use iTunes lookup for show/episode metadata and `episodeUrl`; if needed, resolve audio from RSS enclosure.
- Download audio and run ASR. For multi-speaker episodes, prefer WhisperX with diarization; keep generic `SPEAKER_00/01` labels if roles cannot be proven.
- Descriptions are metadata only, not source text.

## Xiaohongshu

- Resolve short links, scrape public page title/body/image URLs, and OCR visible images.
- Complete content requires available body text plus OCR for all visible long-text images.
- If the public page is incomplete, use an already logged-in browser only to view, expand, scroll, screenshot, and save images. Do not like, comment, follow, send, or modify anything.

## Normalization

- Normalize Chinese metadata, body, OCR, subtitles, and ASR transcript to simplified Chinese.
- Preserve non-Chinese source text in its original language.
- Store new assets under `data/assets/YYYY-MM-DD/` and working JSON/Markdown under `data/working/YYYY-MM-DD/`.
