# Autonomous Vietnamese Dubbing Pipeline

## 1. Mục tiêu

Xây một hệ thống riêng trong MoneyPrinterV2 để tự động:

```text
tìm video nguồn -> tải video -> lồng tiếng Việt -> render -> upload YouTube/TikTok/Facebook
```

Hệ thống mới được phép tái sử dụng uploader đã chạy tốt, nhưng không được thay đổi hoặc gây rủi ro cho pipeline YouTube Shorts hiện tại.

## 2. Nguyên tắc bắt buộc

- Đây là hệ thống riêng, không trộn logic vào `YouTube.generate_video()`.
- Không sửa flow YouTube Shorts hiện tại nếu không bắt buộc.
- Reuse code cũ bằng file/class mới hoặc adapter, không copy bừa vào flow cũ.
- Output của pipeline mới phải nằm trong thư mục riêng theo từng run.
- Lỗi của pipeline mới không được làm hỏng cron/pipeline hiện tại.
- Config mới nằm dưới key riêng: `dub_pipeline`.
- Upload phải có checkpoint để tránh đăng trùng.

## 3. Không lưu trực tiếp vào root `.mp`

Không nên lưu video/audio của pipeline mới trực tiếp vào `.mp`, dù tiện, vì:

- `.mp` đang là temp workspace chung của MoneyPrinterV2.
- `src/cleanup_mp.py` có thể xóa `.mp4`, `.wav`, `.mp3`, `.srt` cũ trong `.mp`.
- Module hiện tại có thể giả định file trong `.mp` là artifact của YouTube Shorts.
- Dùng chung root `.mp` dễ cleanup nhầm, upload nhầm, hoặc va chạm tên file.

Output khuyến nghị:

```text
output/dub_pipeline/VN/{timestamp}_vi/
```

Nếu cần đặt dưới `.mp`, chỉ dùng namespace riêng:

```text
.mp/dub_pipeline/{timestamp}_vi/
```

MVP nên dùng `output/dub_pipeline/...`, rồi truyền `dubbed_video.mp4` vào uploader hiện có.

## 4. Luồng tổng thể

```text
[CRON START]
-> Auto Topic + Keyword
-> Source Discovery
-> Download Video
-> Extract Audio
-> Background Handling
-> ASR
-> Translate to Vietnamese
-> TTS per Segment
-> Timeline Fit + Audio Mix
-> Render Dubbed Video
-> Generate Metadata
-> Upload YouTube/TikTok/Facebook
-> Cleanup Run Artifacts nếu upload thành công
-> PIPELINE COMPLETE
```

## 5. Các bước xử lý

### STEP 0: Auto Topic + Keyword

Nguồn topic/keyword: danh sách trong config, trend Xiaohongshu, Google Trends, hoặc LLM tự sinh. Hệ thống lấy niche/topic theo account hoặc config, sinh nhiều keyword ứng viên, dùng LLM chọn keyword có khả năng viral nhất, rồi chọn voice mặc định theo account/config.

Output: `topic_selection.json`.

### STEP 1: Source Discovery + Download

Thứ tự ưu tiên: Xiaohongshu trước, Douyin sau.

Discovery bằng Playwright:

- Mở browser, có thể dùng browser profile/cookie nếu cần login.
- Search keyword.
- Lấy video candidates.
- Lọc theo chủ đề, duration, engagement, trạng thái chưa xử lý, keyword an toàn.
- Nếu Xiaohongshu fail, fallback Douyin.

Download:

- Ưu tiên Playwright/network capture.
- Nếu có URL trực tiếp và `yt-dlp` hỗ trợ thì dùng `yt-dlp`.
- Nếu candidate fail, thử candidate tiếp theo.

Output:

```text
output/dub_pipeline/VN/{timestamp}_vi/
  candidates.json
  source_metadata.json
  source_video.mp4
```

### STEP 2: Extract Audio

Dùng ffmpeg:

```text
source_video.mp4 -> original_audio.wav
```

Output: `original_audio.wav`.

### STEP 2.5: Background Handling

Modes:

- `duck`: giảm volume audio gốc, ví dụ `-12dB`.
- `demucs`: tách vocal/nhạc, giữ `novocals.wav`.
- `none`: bỏ qua.

Output tùy mode: `background.wav`, `novocals.wav`.

### STEP 3: ASR

Provider: Groq Whisper large-v3.

Output:

```text
transcript_original.json
transcript_original.srt
```

Nếu ASR không nhận được segment nào, pipeline dùng `fallback_transcript_text` để tiếp tục render video thay vì fail run. Trường hợp này ghi thêm `asr_fallback.json` trong thư mục run để review lại nguồn.

Segment schema:

```json
{"index": 1, "start": 0.0, "end": 2.8, "text": "original speech"}
```

### STEP 4: Translate to Vietnamese

Provider: Gemini 2.0 Flash nếu còn quota, fallback Groq LLaMA 3.3 70B.

Output: `transcript_vi.json`.

Mỗi segment thêm:

```json
{"text_vi": "bản dịch tiếng Việt"}
```

### STEP 5: Vietnamese TTS per Segment

Provider: LucyLab API hoặc Vivibe API.

Yêu cầu:

- Tạo audio riêng cho từng segment.
- Auto chỉnh tốc độ để khớp duration gốc.
- Giới hạn speed tối đa, ví dụ `1.3x`.
- Nếu vẫn dài hơn duration, để timeline fitter xử lý.

Output: `segments/seg_001.wav`, `segments/seg_002.wav`, ...

### STEP 6: Timeline Fit + Audio Mix

Xử lý:

- Slow down nếu cần, ví dụ `atempo=0.82`.
- Đặt từng segment vào đúng timestamp.
- Tránh overlap giữa các segment.
- Merge voice tiếng Việt với background music.

Output: `audio_vi_full.wav`, `timeline_plan.json`.

### STEP 7: Render Video

Dùng ffmpeg:

```text
source_video.mp4 + audio_vi_full.wav -> dubbed_video.mp4
```

Output: `dubbed_video.mp4`.

### STEP 8: Generate Metadata

Provider: Gemini nếu còn quota, fallback Groq.

Output: `youtube_metadata.json`, `thumbnail_prompts.txt`, `caption.txt`.

Metadata gồm: `title`, `description`, `hashtags`, source reference, language, topic/keyword.
Title ưu tiên `source_title`, sau đó transcript và trend keyword; lỗi LLM được ghi log thay vì âm thầm dùng title chung.
Pipeline từ chối upload YouTube khi title generic hoặc đã tồn tại trong cache video của tài khoản.

### STEP 9: Upload

Tái sử dụng uploader hiện có: YouTube, TikTok, Facebook Reels. Không sửa flow upload cũ; tạo adapter riêng `DubUploadAdapter`.

Adapter nhận: `dubbed_video.mp4`, `youtube_metadata.json`, `caption.txt`.

Output: `upload_result.json`, gồm YouTube URL, TikTok status, Facebook URL và lỗi nếu có.

### STEP 10: Cleanup Run Artifacts

Nếu `cleanup_after_successful_upload=true`, pipeline chỉ xóa thư mục run sau khi các nền tảng upload đang bật đều trả về `success=true`. Nếu upload bị tắt hoặc có nền tảng fail, giữ nguyên toàn bộ artifact để review/debug.

## 6. Config đề xuất

```json
{
  "dub_pipeline": {
    "enabled": true,
    "sources": ["xiaohongshu"],
    "topics": [],
    "topic_mode": "trend",
    "fallback_topic": "",
    "output_root": "output/dub_pipeline",
    "cleanup_after_successful_upload": true,
    "language": "vi",
    "voice": "default",
    "background_mode": "duck",
    "max_video_duration_seconds": 90,
    "min_engagement": 1000,
    "fallback_transcript_text": "Xem hết video này nhé.",
    "upload": {
      "youtube": true,
      "tiktok": true,
      "facebook_reels": true
    }
  }
}
```

## 7. File/class mới đề xuất

```text
src/classes/DubPipeline.py
src/classes/DubTopicPlanner.py
src/classes/XiaohongshuDiscovery.py
src/classes/DouyinDiscovery.py
src/classes/DubVideoDownloader.py
src/classes/DubAudioProcessor.py
src/classes/DubAsr.py
src/classes/DubTranslator.py
src/classes/DubTts.py
src/classes/DubTimelineMixer.py
src/classes/DubVideoRenderer.py
src/classes/DubMetadata.py
src/classes/DubUploadAdapter.py
```

Cron riêng khuyến nghị cho MVP:

```text
src/dub_cron.py
python3 src/dub_cron.py <account_id> <model>
```

Dùng file cron riêng trước để giảm rủi ro ảnh hưởng `src/cron.py`.

## 8. MVP acceptance

MVP phải chạy được end-to-end:

```text
auto keyword -> Xiaohongshu/Douyin discovery -> download -> dub -> upload
```

Run thành công khi có:

```text
source_video.mp4
transcript_original.json
transcript_vi.json
audio_vi_full.wav
dubbed_video.mp4
youtube_metadata.json
upload_result.json
```

Và log:

```text
PIPELINE COMPLETE
```

## 9. Kiểm thử tối thiểu

- Chạy preflight config.
- Chạy 1 run upload off để kiểm tra render.
- Chạy 1 run upload on với video ngắn.
- Đảm bảo YouTube Shorts flow cũ vẫn chạy như trước.
- Đảm bảo file dubbing không bị cleanup `.mp` xóa nhầm.

## 10. Rủi ro

- Xiaohongshu/Douyin có thể đổi DOM hoặc chặn bot.
- Có thể cần login/cookie/browser profile.
- Download có thể fail với một số video.
- ASR/translation/TTS có thể vượt quota.
- Video nguồn có thể có bản quyền, cần lọc nguồn hợp lệ trước khi upload public.

## 11. Kết luận

Tên hệ thống:

```text
Autonomous Vietnamese Dubbing Pipeline
```

Nó chạy độc lập với YouTube Shorts pipeline hiện tại và chỉ reuse uploader ổn định thông qua adapter riêng.
