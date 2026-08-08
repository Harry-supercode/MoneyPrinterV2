from selenium.webdriver.firefox.options import Options


def apply_firefox_profile(options: Options, profile_path: str) -> None:
    options.add_argument("-profile")
    options.add_argument(profile_path)
