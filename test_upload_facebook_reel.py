from src.classes.FacebookReels import FacebookReels

PROFILE_DIR = "/Users/harrytrinhtvf/Library/Application Support/Firefox/Profiles/qe8d67zg.default-release"

VIDEO_PATH = "/Users/harrytrinhtvf/Documents/HarryTrinh-TVF/Kombu/MoneyPrinterV2/.mp/fd5086d2-dfcd-4065-8a64-0d63eef88396.mp4"

caption = "Test upload from MoneyPrinterV2 #ev #finance #reels"

bot = FacebookReels(PROFILE_DIR)
bot.upload_profile_reel(VIDEO_PATH, caption)
