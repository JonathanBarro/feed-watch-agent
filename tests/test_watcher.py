import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import feeds  # noqa: E402
import main  # noqa: E402
import notify  # noqa: E402
import state  # noqa: E402

RSS = """<rss version="2.0"><channel>
<item><title>Release 2.0</title><link>https://x.test/2</link><guid>id-2</guid>
<pubDate>Mon, 01 Jan 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Big &amp;amp; new&lt;/p&gt;</description></item>
<item><title>Security fix</title><link>https://x.test/1</link><description>patch</description></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>atom-1</id><title>Atom post</title><link href="https://a.test/1"/>
<updated>2026-01-02T00:00:00Z</updated><summary>hello</summary></entry></feed>"""


class ParsingTests(unittest.TestCase):
    def test_rss_items(self):
        items = feeds.parse_feed(RSS, "Blog")
        self.assertEqual([i["id"] for i in items], ["id-2", "https://x.test/1"])  # guid, else link
        self.assertEqual(items[0]["summary"], "Big & new")  # html stripped and unescaped
        self.assertEqual(items[0]["feed"], "Blog")

    def test_atom_items(self):
        items = feeds.parse_feed(ATOM, "A")
        self.assertEqual(items[0]["id"], "atom-1")
        self.assertEqual(items[0]["url"], "https://a.test/1")

    def test_invalid_xml_returns_empty(self):
        self.assertEqual(feeds.parse_feed("<not xml", "X"), [])

    def test_keywords(self):
        item = {"title": "Security fix", "summary": "patch"}
        self.assertTrue(feeds.matches_keywords(item, []))
        self.assertTrue(feeds.matches_keywords(item, ["SECURITY"]))
        self.assertFalse(feeds.matches_keywords(item, ["release"]))

    def test_failed_download_does_not_raise(self):
        import requests
        with mock.patch.object(feeds.requests, "get", side_effect=requests.ConnectionError("down")):
            self.assertEqual(feeds.fetch_feed({"name": "F", "url": "https://x.test"}), [])


class DigestTests(unittest.TestCase):
    def test_digest_escapes_html(self):
        item = {"feed": "F", "title": "<script>x</script>", "date": "", "summary": "", "url": "https://x.test"}
        subject, html, text = notify.build_digest([item], date(2026, 1, 1), "Watch")
        self.assertIn("1 new update", subject)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"
        self.config = {"title": "T", "feeds": [{"name": "F", "url": "u"}], "keywords": []}
        patches = [
            mock.patch.object(main, "STATE_PATH", self.state_path),
            mock.patch.object(main.yaml, "safe_load", side_effect=lambda _: self.config),
            mock.patch.object(Path, "read_text", lambda p, **k: "" if p == main.CONFIG_PATH else Path.read_bytes(p).decode()),
            mock.patch.object(main.sys, "argv", ["main"]),
            mock.patch.dict(main.os.environ, {"SMTP_USER": "u", "SMTP_PASSWORD": "p", "RECIPIENTS": "a@x.test, b@x.test"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _items(self, *ids):
        return [{"id": i, "title": i, "date": "", "summary": "", "url": "https://x.test/" + i, "feed": "F"} for i in ids]

    def test_seed_then_only_new_items_are_sent(self):
        with mock.patch.object(main, "fetch_feed", return_value=self._items("a", "b")), \
             mock.patch.object(main, "send_email") as send:
            self.assertEqual(main.main(), 0)           # first run: seed
            send.assert_not_called()
            self.assertTrue(state.load_state(self.state_path)["initialized"])

            self.assertEqual(main.main(), 0)           # nothing new
            send.assert_not_called()

        with mock.patch.object(main, "fetch_feed", return_value=self._items("a", "b", "c")), \
             mock.patch.object(main, "send_email") as send:
            self.assertEqual(main.main(), 0)
            send.assert_called_once()
            self.assertEqual(send.call_args.args[4], ["a@x.test", "b@x.test"])  # recipients from env
            self.assertIn("c", state.load_state(self.state_path)["seen_ids"])

    def test_failed_send_keeps_items_for_next_run(self):
        state.save_state(self.state_path, {"initialized": True, "seen_ids": ["a"]})
        with mock.patch.object(main, "fetch_feed", return_value=self._items("a", "b")), \
             mock.patch.object(main, "send_email", side_effect=OSError("smtp down")):
            self.assertEqual(main.main(), 1)
        self.assertEqual(state.load_state(self.state_path)["seen_ids"], ["a"])  # "b" not lost

    def test_missing_secrets_fails_cleanly(self):
        state.save_state(self.state_path, {"initialized": True, "seen_ids": []})
        with mock.patch.object(main, "fetch_feed", return_value=self._items("a")), \
             mock.patch.dict(main.os.environ, {"RECIPIENTS": ""}):
            self.assertEqual(main.main(), 1)


if __name__ == "__main__":
    unittest.main()
