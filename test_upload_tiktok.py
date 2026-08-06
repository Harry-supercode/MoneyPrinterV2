from src.classes.TikTok import TikTok

PROFILE_DIR = "/Users/harrytrinhtvf/Library/Application Support/Firefox/Profiles/qe8d67zg.default-release"

VIDEO_PATH = "/Users/harrytrinhtvf/Documents/HarryTrinh-TVF/Kombu/MoneyPrinterV2/.mp/fd5086d2-dfcd-4065-8a64-0d63eef88396.mp4"

caption = "Test upload from MoneyPrinterV2 #ev #finance #shorts"

bot = TikTok(PROFILE_DIR)
bot.upload_video(VIDEO_PATH, caption)
