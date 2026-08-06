import os
import sys
import types
import unittest
from unittest.mock import Mock
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

fake_srt_equalizer = types.ModuleType("srt_equalizer")
fake_srt_equalizer.equalize_srt_file = lambda *args, **kwargs: None
sys.modules.setdefault("srt_equalizer", fake_srt_equalizer)

import trends


class GoogleTrendsTests(unittest.TestCase):
    def test_fetch_google_trends_keywords_parses_rss_titles(self) -> None:
        rss = """
        <rss>
          <channel>
            <item>
              <title>VinFast stock</title>
              <description>EV finance news</description>
            </item>
            <item>
              <title>Football match</title>
              <description>Sports</description>
            </item>
          </channel>
        </rss>
        """
        response = Mock()
        response.text = rss
        response.raise_for_status.return_value = None

        with (
            patch("trends.requests.get", return_value=response),
            patch("trends._write_trends_cache"),
        ):
            keywords = trends.fetch_google_trends_keywords(
                geo="VN",
                hl="vi",
                max_items=10,
            )

        self.assertEqual(keywords, ["VinFast stock", "Football match"])

    def test_fetch_google_trends_uses_short_connect_and_read_timeouts(self) -> None:
        response = Mock()
        response.text = "<rss><channel></channel></rss>"
        response.raise_for_status.return_value = None

        with patch("trends.requests.get", return_value=response) as get_mock:
            trends.fetch_google_trends_keywords(geo="VN", hl="vi")

        self.assertEqual(get_mock.call_args.kwargs["timeout"], (3.05, 8))

    def test_fetch_google_trends_keywords_applies_category_filter(self) -> None:
        rss = """
        <rss>
          <channel>
            <item>
              <title>VinFast stock</title>
              <description>EV finance news</description>
            </item>
            <item>
              <title>Football match</title>
              <description>Sports</description>
            </item>
          </channel>
        </rss>
        """
        response = Mock()
        response.text = rss
        response.raise_for_status.return_value = None

        with (
            patch("trends.requests.get", return_value=response),
            patch("trends._write_trends_cache"),
        ):
            keywords = trends.fetch_google_trends_keywords(
                geo="VN",
                hl="vi",
                category_filter="finance",
                max_items=10,
            )

        self.assertEqual(keywords, ["VinFast stock"])

    def test_filter_safe_trend_keywords_blocks_unsafe_terms_without_accents(self) -> None:
        keywords = [
            "xem bong da live",
            "VinFast stock",
            "nhà cái hôm nay",
            "AI finance news",
        ]

        safe_keywords = trends.filter_safe_trend_keywords(
            keywords,
            unsafe_keywords=["xem bóng đá", "nhà cái"],
        )

        self.assertEqual(safe_keywords, ["VinFast stock", "AI finance news"])

    def test_find_unsafe_keyword_ignores_vietnamese_accents(self) -> None:
        matched_keyword = trends.find_unsafe_keyword(
            "xem bong da live",
            ["xem bóng đá"],
        )

        self.assertEqual(matched_keyword, "xem bóng đá")

    @patch("trends.get_youtube_trends_config")
    def test_get_trend_topic_seed_falls_back_when_disabled(self, config_mock) -> None:
        config_mock.return_value = {"enabled": False}

        topic_seed = trends.get_trend_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "Technology, EV, Finance")

    @patch("trends.fetch_google_trends_keywords")
    @patch("trends.get_youtube_trends_config")
    def test_get_trend_topic_seed_uses_google_trends(self, config_mock, fetch_mock) -> None:
        config_mock.return_value = {
            "enabled": True,
            "source": "google_trending_rss",
            "geo": "VN",
            "hl": "vi",
            "category_filter": "",
            "max_items": 10,
            "safety_filter_enabled": True,
            "unsafe_keywords": [],
        }
        fetch_mock.return_value = ["VinFast stock"]

        topic_seed = trends.get_trend_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "VinFast stock")

    @patch("trends.fetch_google_trends_keywords")
    @patch("trends.get_youtube_trends_config")
    def test_get_trend_topic_seed_falls_back_when_all_trends_are_unsafe(
        self,
        config_mock,
        fetch_mock,
    ) -> None:
        config_mock.return_value = {
            "enabled": True,
            "source": "google_trending_rss",
            "geo": "VN",
            "hl": "vi",
            "category_filter": "",
            "max_items": 10,
            "safety_filter_enabled": True,
            "unsafe_keywords": ["xem bóng đá", "cá cược"],
        }
        fetch_mock.return_value = ["xem bong da live", "cá cược bóng đá"]

        topic_seed = trends.get_trend_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "Technology, EV, Finance")

    @patch("trends._read_trends_cache", return_value=["cached AI trend"])
    @patch("trends.fetch_google_trends_keywords", side_effect=OSError("DNS unavailable"))
    @patch("trends.get_youtube_trends_config")
    def test_get_trend_topic_seed_uses_cache_when_network_fails(
        self,
        config_mock,
        _fetch_mock,
        _cache_mock,
    ) -> None:
        config_mock.return_value = {
            "enabled": True,
            "source": "google_trending_rss",
            "geo": "VN",
            "hl": "vi",
            "category_filter": "",
            "max_items": 10,
            "safety_filter_enabled": True,
            "unsafe_keywords": [],
        }

        topic_seed = trends.get_trend_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "cached AI trend")

    @patch("trends.random.choice", side_effect=lambda values: values[0])
    @patch("trends.get_youtube_brand_topics_config")
    def test_get_brand_topic_seed_uses_configured_concepts(
        self,
        config_mock,
        _choice_mock,
    ) -> None:
        config_mock.return_value = {
            "enabled": True,
            "keywords": ["HIEMEE business ecosystem"],
            "concepts": ["Cashflow -> Technology -> Assets"],
        }

        topic_seed = trends.get_brand_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "Cashflow -> Technology -> Assets")

    @patch("trends.get_youtube_brand_topics_config")
    def test_get_brand_topic_seed_falls_back_when_empty(self, config_mock) -> None:
        config_mock.return_value = {
            "enabled": True,
            "keywords": [],
            "concepts": [],
        }

        topic_seed = trends.get_brand_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "Technology, EV, Finance")

    @patch("trends.get_trend_topic_seed")
    @patch("trends.get_brand_topic_seed")
    @patch("trends.get_youtube_brand_topics_config")
    def test_get_youtube_topic_seed_prefers_brand_topics(
        self,
        config_mock,
        brand_seed_mock,
        trend_seed_mock,
    ) -> None:
        config_mock.return_value = {
            "enabled": True,
            "keywords": ["HIEMEE business ecosystem"],
            "concepts": [],
        }
        brand_seed_mock.return_value = "HIEMEE business ecosystem"

        topic_seed = trends.get_youtube_topic_seed("Technology, EV, Finance")

        self.assertEqual(topic_seed, "HIEMEE business ecosystem")
        trend_seed_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
