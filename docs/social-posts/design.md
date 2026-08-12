# Social Posts Design

## Architecture

The feature is a standalone pipeline:

1. `src/social_post_cron.py`
2. `SocialPostPipeline`
3. `SocialPostGenerator`
4. `FacebookPost`
5. `YouTubeCommunityPost`
6. `scripts/run_social_post_job.sh`
7. `scripts/random_scheduler.py` health integration

## Flow

```text
social_post_cron.py
  -> load social_posts config
  -> select Ollama model
  -> generate post draft
  -> save draft JSON under output/social_posts
  -> publish enabled platforms through Selenium
  -> write .mp/social_posts_state.json
```

## Browser automation

Both platform classes use Selenium with a configured Firefox profile. They do not own account login. The VPS operator must log in once through the same profile before running automation.

Facebook opens `platforms.facebook.create_url`, activates a post composer, sets text, optionally attaches an image, then clicks Post/Publish.

YouTube opens `platforms.youtube.create_url`, finds a Community/Post composer, sets text, optionally attaches an image, then clicks Post/Publish. To reuse the same content after a Facebook run, pass the Facebook draft JSON path back into `src/social_post_cron.py` with `--platform youtube --draft-path <path>`.

The YouTube implementation intentionally relies on generic selectors because YouTube Community UI changes. It must be verified manually on the VPS before scheduler publishing is enabled.

## Scheduler gate

`random_scheduler.py` can launch `social_post`, but the runner calls `src/social_post_cron.py` without bypass flags. The cron script refuses scheduled publishing unless:

```json
"social_posts": {
  "enabled": true,
  "automation_verified": true
}
```

This lets code be deployed now without accidentally posting.
