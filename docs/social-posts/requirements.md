# Social Posts Requirements

## Scope

Add a separate browser-automation pipeline for publishing text/image posts without changing the existing YouTube Shorts, Dub, TikTok, or Facebook Reels upload flows.

## Target behavior

- Generate a short brand-safe social post from configured topics or existing HIEMEE brand topics.
- Save every generated draft before publishing.
- Publish Facebook text/image posts first.
- Add YouTube Community Post automation after the Facebook path exists.
- Integrate the job into the existing random scheduler only behind an explicit `automation_verified` gate.
- Defer the social-post job when YouTube Shorts or Dub jobs are active.

## Non-goals

- Do not use Facebook Graph API or YouTube Data API.
- Do not modify the working video upload behavior.
- Do not auto-enable scheduled social posts by default.
- Do not guarantee browser automation pass on local; final pass must happen on the VPS with the logged-in browser profile.

## Configuration requirements

- `social_posts.enabled`: enables manual pipeline execution.
- `social_posts.automation_verified`: must be true before scheduled publishing is allowed.
- `social_posts.browser_profile`: Firefox profile path on the VPS.
- `social_posts.platforms.facebook.enabled`: controls Facebook post publishing.
- `social_posts.platforms.facebook.create_url`: Facebook Page/Profile URL or composer URL to open.
- `social_posts.platforms.youtube.enabled`: controls YouTube Community Post publishing.
- `social_posts.platforms.youtube.create_url`: YouTube post/community URL to open.
- `social_posts.image_paths`: optional absolute or repo-relative image paths.

## Safety rules

- Use a separate runner, lock, log, and state files:
  - `scripts/run_social_post_job.sh`
  - `/tmp/moneyprinterv2-social-post.lock`
  - `social_posts.log`
  - `.mp/social_posts_state.json`
- If another MoneyPrinterV2 browser job is active, scheduler must defer.
- Scheduler integration must not publish unless `social_posts.automation_verified=true`.
