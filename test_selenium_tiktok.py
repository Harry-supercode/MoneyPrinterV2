import os
import time

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager

PROFILE_DIR = "/Users/harrytrinhtvf/Library/Application Support/Firefox/Profiles/qe8d67zg.default-release"

if not os.path.isdir(PROFILE_DIR):
    raise ValueError(f"Firefox profile not found: {PROFILE_DIR}")

options = Options()
options.add_argument("-profile")
options.add_argument(PROFILE_DIR)

service = Service(GeckoDriverManager().install())

browser = webdriver.Firefox(service=service, options=options)

browser.get("https://www.tiktok.com/upload")

time.sleep(120)

browser.quit()
