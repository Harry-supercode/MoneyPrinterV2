# Configuration

All your configurations will be in a file in the root directory, called `config.json`, which is a copy of `config.example.json`. You can change the values in `config.json` to your liking.

## Values

- `verbose`: `boolean` - If `true`, the application will print out more information.
- `firefox_profile`: `string` - The path to your Firefox profile. This is used to use your Social Media Accounts without having to log in every time you run the application.
- `headless`: `boolean` - If `true`, the application will run in headless mode. This means that the browser will not be visible.
- `ollama_base_url`: `string` - Base URL of your Ollama server (default: `http://127.0.0.1:11434`). For localhost, the app automatically starts `ollama serve` when the endpoint is offline; remote URLs are never started locally.
- `ollama_model`: `string` - Ollama model to use for text generation (e.g. `llama3.2:3b`). If empty, the app queries Ollama at startup and lets you pick from the available models interactively.
- `twitter_language`: `string` - The language that will be used to generate & post tweets.
- `youtube_english_mode`: `object` - Optional switch for generated YouTube Shorts and the Dub pipeline. If enabled, Shorts ideas, scripts, titles, descriptions, Dub translations, Dub metadata, subtitles, and Edge TTS voice use English regardless of the account or Dub language.
    - `enabled`: `boolean` - If `true`, force generated Shorts and Dub output content/voice to English.
    - `language`: `string` - Language label sent to the LLM. Default is `English`.
    - `voice`: `string` - Primary Edge TTS voice. Default is `en-US-GuyNeural`.
    - `fallback_voices`: `string[]` - Backup Edge TTS voices if the primary voice fails.
- `youtube_trends`: `object` - Optional trend source for YouTube idea generation. If disabled or unavailable, the account niche is used.
    - Successful RSS responses are cached in `.mp/google_trends_cache.json`; transient DNS/network failures reuse the latest matching cache before falling back.
    - `enabled`: `boolean` - If `true`, use a trend keyword as the YouTube topic seed.
    - `source`: `string` - Trend source. Currently supports `google_trending_rss`.
    - `geo`: `string` - Google Trends region code, for example `VN` or `US`.
    - `hl`: `string` - Google Trends language code, for example `vi` or `en-US`.
    - `category_filter`: `string` - Optional text filter applied to trend titles/descriptions.
    - `max_items`: `number` - Maximum number of trends to consider before choosing one randomly.
    - `safety_filter_enabled`: `boolean` - If `true`, skip unsafe trend keywords before sending a topic seed to the AI.
    - `unsafe_keywords`: `string[]` - Blocklist for sensitive trend topics such as betting, gambling, adult, drugs, violence, scams, piracy, and unsafe political/war terms. Matching is case-insensitive and ignores Vietnamese accents.
- `youtube_brand_topics`: `object` - Optional brand-safe topic source for YouTube Shorts. When enabled, this takes precedence over `youtube_trends` so cron can focus on a controlled brand ecosystem instead of broad daily trends.
    - `enabled`: `boolean` - If `true`, use the configured brand keywords/concepts as the YouTube topic seed.
    - `keywords`: `string[]` - Short brand, product, and industry keywords.
    - `concepts`: `string[]` - Longer brand-safe content angles for the AI idea prompt.
- `nanobanana2_api_base_url`: `string` - Nano Banana 2 API base URL (default: `https://generativelanguage.googleapis.com/v1beta`).
- `nanobanana2_api_key`: `string` - API key for Nano Banana 2 (Gemini image API). If empty, MPV2 falls back to environment variable `GEMINI_API_KEY`.
- `nanobanana2_model`: `string` - Nano Banana 2 model name (default: `gemini-3.1-flash-image-preview`).
- `nanobanana2_aspect_ratio`: `string` - Aspect ratio for generated images (default: `9:16`).
- `luma_api_key`: `string` - Optional Luma API key for legacy AI video hook generation. If empty, MPV2 falls back to `LUMA_API_KEY`.
- `runway_api_key`: `string` - Runway API key for optional AI video hook generation. If empty, MPV2 falls back to `RUNWAYML_API_SECRET` or `RUNWAY_API_KEY`.
- `ai_video`: `object` - Optional AI image-to-video hook for the first seconds of each generated video.
    - `enabled`: `boolean` - If `true`, generate a short AI cinematic hook before the normal image/Pexels motion sequence.
    - `provider`: `string` - Supports `runway` and legacy `luma`.
    - `mode`: `string` - Currently supports `hook_only`.
    - `model`: `string` - Runway model, for example `gen4.5` or `gen4_turbo`.
    - `duration`: `string` - Clip duration in seconds, for example `5`.
    - `resolution`: `string` - Legacy Luma output resolution, for example `720p`.
    - `aspect_ratio`: `string` - Legacy Luma output aspect ratio, recommended `9:16`.
    - `ratio`: `string` - Runway output ratio, recommended `720:1280` for vertical shorts/reels.
    - `poll_interval_seconds`: `number` - Seconds between generation status checks.
    - `timeout_seconds`: `number` - Maximum wait time for an AI video generation.
- `threads`: `number` - The amount of threads that will be used to execute operations, e.g. writing to a file using MoviePy.
- `is_for_kids`: `boolean` - If `true`, the application will upload the video to YouTube Shorts as a video for kids.
- `google_maps_scraper`: `string` - The URL to the Google Maps scraper. This will be used to scrape Google Maps for local businesses. It is recommended to use the default value.
- `zip_url`: `string` - The URL to the ZIP file that contains the to be used Songs for the YouTube Shorts Automater.
- `email`: `object`:
    - `smtp_server`: `string` - Your SMTP server.
    - `smtp_port`: `number` - The port of your SMTP server.
    - `username`: `string` - Your email address.
    - `password`: `string` - Your email password.
- `google_maps_scraper_niche`: `string` - The niche you want to scrape Google Maps for.
- `scraper_timeout`: `number` - The timeout for the Google Maps scraper.
- `outreach_message_subject`: `string` - The subject of your outreach message. `{{COMPANY_NAME}}` will be replaced with the company name.
- `outreach_message_body_file`: `string` - The file that contains the body of your outreach message, should be HTML. `{{COMPANY_NAME}}` will be replaced with the company name.
- `stt_provider`: `string` - Provider for subtitle transcription. Default is `local_whisper`. Options:
    * `local_whisper`
    * `third_party_assemblyai`
- `whisper_model`: `string` - Whisper model for local transcription (for example `base`, `small`, `medium`, `large-v3`).
- `whisper_device`: `string` - Device for local Whisper (`auto`, `cpu`, `cuda`).
- `whisper_compute_type`: `string` - Compute type for local Whisper (`int8`, `float16`, etc.).
- `assembly_ai_api_key`: `string` - Your Assembly AI API key. Get yours from [here](https://www.assemblyai.com/app/).
- `tts_voice`: `string` - Primary Edge TTS voice for normal Shorts when `youtube_english_mode.enabled` is `false`. Default local config uses `vi-VN-NamMinhNeural`.
- `font`: `string` - The font that will be used to generate images. This should be a `.ttf` file in the `fonts/` directory.
- `imagemagick_path`: `string` - The path to the ImageMagick binary. This is used by MoviePy to manipulate images. Install ImageMagick from [here](https://imagemagick.org/script/download.php) and set the path to the `magick.exe` on Windows, or on Linux/MacOS the path to `convert` (usually /usr/bin/convert).
- `script_sentence_length`: `number` - The number of sentences in the generated video script (default: `4`).
- `post_bridge`: `object`:
    - `enabled`: `boolean` - Enables Post Bridge cross-posting after successful YouTube uploads.
    - `api_key`: `string` - Your Post Bridge API key. If empty, MPV2 falls back to `POST_BRIDGE_API_KEY`.
    - `platforms`: `string[]` - Platforms to target. Supported values in v1 are `tiktok` and `instagram`.
    - `account_ids`: `number[]` - Optional fixed Post Bridge account IDs to avoid account-selection prompts.
    - `auto_crosspost`: `boolean` - If `true`, cross-post automatically after a successful YouTube upload. If `false`, interactive runs ask and cron runs skip.
- `random_scheduler`: `object` - Optional daily random scheduler for cron. Run `scripts/run_random_scheduler.sh` from cron every 10-15 minutes; it generates non-overlapping daily slots and launches the real YouTube/Dub jobs only when a slot is due.
    - `enabled`: `boolean` - If `true`, random scheduling is active.
    - `daily_job_limit`: `number` - Total slots per day.
    - `window_start` / `window_end`: `HH:MM` - Allowed local time window.
    - `min_gap_minutes`: `number` - Minimum spacing between generated slots.
    - `tick_grace_minutes`: `number` - How long a cron tick may be late and still launch a due slot.
    - `override_platform_uploads`: `boolean` - If `false`, the scheduler only randomizes job time/order and leaves each job's upload behavior unchanged. If `true`, the scheduler may use `platform_limits` to set upload env overrides.
    - `jobs`: `object[]` - Job mix, for example 3 `youtube_short` and 3 `dub_pipeline`.
    - `platform_limits`: `object` - Optional daily social upload caps used only when `override_platform_uploads` is `true`.
    - `launchers`: `object` - Direct job runner paths for each job.
    - `launch_probe_seconds`: `number` - Seconds to wait for a runner pid, lock, or START log before marking a launch as healthy.

## Example

```json
{
  "verbose": true,
  "firefox_profile": "",
  "headless": false,
  "ollama_base_url": "http://127.0.0.1:11434",
  "ollama_model": "",
  "twitter_language": "English",
  "youtube_english_mode": {
    "enabled": false,
    "language": "English",
    "voice": "en-US-GuyNeural",
    "fallback_voices": ["en-US-JennyNeural"]
  },
  "youtube_trends": {
    "enabled": false,
    "source": "google_trending_rss",
    "geo": "VN",
    "hl": "vi",
    "category_filter": "",
    "max_items": 10,
    "safety_filter_enabled": true,
    "unsafe_keywords": [
      "betting",
      "sportsbook",
      "casino",
      "cá cược",
      "nhà cái",
      "xem bóng đá",
      "xem bong da",
      "bong da live",
      "trực tiếp bóng đá",
      "18+",
      "sex",
      "porn",
      "ma túy",
      "vũ khí",
      "lừa đảo",
      "hack",
      "war",
      "terror",
      "suicide"
    ]
  },
  "youtube_brand_topics": {
    "enabled": true,
    "keywords": [
      "HIEMEE business ecosystem",
      "Cashflow -> Technology -> Assets",
      "Hie-Palace hospitality business",
      "Hie-Software business operating system",
      "HieRealty real estate technology"
    ],
    "concepts": [
      "HIEMEE is building a business ecosystem where restaurant cashflow, software systems, and real estate assets reinforce each other.",
      "Hie-Palace creates real customer demand, Hie-Software turns operations into systems, and HieRealty compounds value into long-term assets."
    ]
  },
  "nanobanana2_api_base_url": "https://generativelanguage.googleapis.com/v1beta",
  "nanobanana2_api_key": "",
  "nanobanana2_model": "gemini-3.1-flash-image-preview",
  "nanobanana2_aspect_ratio": "9:16",
  "luma_api_key": "",
  "runway_api_key": "",
  "ai_video": {
    "enabled": false,
    "provider": "runway",
    "mode": "hook_only",
    "model": "gen4.5",
    "duration": "5",
    "resolution": "720p",
    "aspect_ratio": "9:16",
    "ratio": "720:1280",
    "poll_interval_seconds": 8,
    "timeout_seconds": 600
  },
  "threads": 2,
  "zip_url": "",
  "is_for_kids": false,
  "google_maps_scraper": "https://github.com/gosom/google-maps-scraper/archive/refs/tags/v0.9.7.zip",
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "",
    "password": ""
  },
  "google_maps_scraper_niche": "",
  "scraper_timeout": 300,
  "outreach_message_subject": "I have a question...",
  "outreach_message_body_file": "outreach_message.html",
  "stt_provider": "local_whisper",
  "whisper_model": "base",
  "whisper_device": "auto",
  "whisper_compute_type": "int8",
  "assembly_ai_api_key": "",
  "tts_voice": "Jasper",
  "font": "bold_font.ttf",
  "imagemagick_path": "Path to magick.exe or on linux/macOS just /usr/bin/convert",
  "script_sentence_length": 4,
  "post_bridge": {
    "enabled": false,
    "api_key": "",
    "platforms": ["tiktok", "instagram"],
    "account_ids": [],
    "auto_crosspost": false
  },
  "random_scheduler": {
    "enabled": true,
    "daily_job_limit": 6,
    "window_start": "08:30",
    "window_end": "22:30",
    "min_gap_minutes": 120,
    "tick_grace_minutes": 20,
    "override_platform_uploads": false,
    "jobs": [
      {
        "name": "youtube_short",
        "count": 3
      },
      {
        "name": "dub_pipeline",
        "count": 3
      }
    ],
    "platform_limits": {
      "facebook_reels": 2,
      "tiktok": 2
    },
    "launchers": {
      "youtube_short": "/Users/harrytrinhtvf/Library/Application Support/MoneyPrinterV2/run_youtube_short_job.sh",
      "dub_pipeline": "/Users/harrytrinhtvf/Library/Application Support/MoneyPrinterV2/run_dub_pipeline_job.sh"
    },
    "launch_probe_seconds": 8
  }
}
```

## Environment Variable Fallbacks

- `GEMINI_API_KEY`: used when `nanobanana2_api_key` is empty.
- `POST_BRIDGE_API_KEY`: used when `post_bridge.api_key` is empty.

Example:

```bash
export GEMINI_API_KEY="your_api_key_here"
export POST_BRIDGE_API_KEY="your_post_bridge_api_key_here"
```

See [PostBridge.md](./PostBridge.md) for the full Post Bridge setup and behavior details.
