from playwright.sync_api import sync_playwright

PROFILE_DIR = "/Users/harrytrinhtvf/Library/Application Support/Firefox/Profiles/qe8d67zg.default-release"

with sync_playwright() as p:
    context = p.firefox.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
    )

    page = context.new_page()

    page.goto("https://www.tiktok.com")
    page.wait_for_timeout(60000)

    context.close()
