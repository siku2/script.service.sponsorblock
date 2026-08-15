import sys
import types
import unittest
from unittest import mock


if "xbmc" not in sys.modules:
    xbmc = types.ModuleType("xbmc")
    xbmc.getInfoLabel = mock.Mock(return_value="")
    xbmc.executeJSONRPC = mock.Mock(return_value='{"result":{"item":{}}}')
    sys.modules["xbmc"] = xbmc


from resources.lib.apis import youtube_api
from resources.lib.apis.invidious_api import InvidiousApi
from resources.lib.utils import xbmc as xbmc_utils


class YouTubeUrlTests(unittest.TestCase):
    def test_current_plugin_query_url(self):
        self.assertEqual(
            youtube_api.video_id_from_url(
                "plugin://plugin.video.youtube/play/?video_id=dQw4w9WgXcQ"
            ),
            "dQw4w9WgXcQ",
        )

    def test_plugin_path_url(self):
        self.assertEqual(
            youtube_api.video_id_from_url(
                "plugin://plugin.video.youtube/play/dQw4w9WgXcQ"
            ),
            "dQw4w9WgXcQ",
        )

    def test_browser_urls(self):
        self.assertEqual(
            youtube_api.video_id_from_url(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=4"
            ),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(
            youtube_api.video_id_from_url("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_missing_query_is_not_an_error(self):
        self.assertIsNone(
            youtube_api.video_id_from_url("plugin://plugin.video.youtube/play/")
        )

    @mock.patch.object(youtube_api, "get_playing_file_path")
    @mock.patch.object(youtube_api, "get_player_item")
    def test_uses_original_item_file_after_stream_resolution(self, item, playing_file):
        playing_file.return_value = "https://rr1.googlevideo.com/videoplayback"
        item.return_value = {
            "file": "plugin://plugin.video.youtube/play/?video_id=dQw4w9WgXcQ"
        }
        self.assertEqual(YouTubeApi().get_video_id(), "dQw4w9WgXcQ")


class PlaybackSourceTests(unittest.TestCase):
    @mock.patch.object(xbmc_utils, "get_playing_file_path")
    def test_googlevideo_stream_maps_back_to_youtube(self, playing_file):
        playing_file.return_value = "https://rr1.googlevideo.com/videoplayback"
        self.assertEqual(xbmc_utils.get_playing_addon(), "plugin.video.youtube")

    @mock.patch(
        "resources.lib.apis.invidious_api.get_playing_file_path",
        return_value="plugin://plugin.video.invidious/?action=video",
    )
    def test_invidious_missing_video_id_is_not_an_error(self, _playing_file):
        self.assertIsNone(InvidiousApi().get_video_id())


YouTubeApi = youtube_api.YouTubeApi


if __name__ == "__main__":
    unittest.main()
