from .DubBrowserDiscovery import DubBrowserDiscovery


class DouyinDiscovery(DubBrowserDiscovery):
    source_name = "douyin"
    search_url_template = "https://www.douyin.com/search/{keyword}?type=video"
    allowed_domains = ("douyin.com", "iesdouyin.com")
    url_markers = ("/video/", "/note/", "/share/video/", "/search/")
