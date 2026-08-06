from .DubBrowserDiscovery import DubBrowserDiscovery


class XiaohongshuDiscovery(DubBrowserDiscovery):
    source_name = "xiaohongshu"
    search_url_template = "https://www.xiaohongshu.com/search_result?keyword={keyword}"
    explore_url_template = "https://www.rednote.com/explore?channel_id=homefeed_recommend"
    allowed_domains = ("xiaohongshu.com", "rednote.com", "xhslink.com")
    url_markers = ("/search_result/", "/explore/", "/discovery/item/", "xhslink.com")

    def _discovery_url(self, keyword: str) -> str:
        if self.config.get("discovery_mode", "explore") == "explore":
            return self.explore_url_template
        return super()._discovery_url(keyword)
