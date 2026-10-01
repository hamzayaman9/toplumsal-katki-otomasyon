import unittest

from katki.crawl import _body_matches_title, _detail_date, _parse_dt, normalize_title
from katki.list_rules import collect_links, deterministic_rule, links_for_rule


class HtmlAdaptorTests(unittest.TestCase):
    def test_repeated_cards_exclude_menu(self) -> None:
        page = (
            '<div class="mainMenu"><a href="/haberler">Bütün haberler</a></div>'
            + "".join(
                f'<div class="news-card"><a href="/haber/{i}">Önemli haber başlığı {i}</a></div>'
                for i in range(3)
            )
        )
        links = collect_links(page.encode(), "https://ornek.test/haberler")
        rule = deterministic_rule(links)
        self.assertIsNotNone(rule)
        self.assertEqual(len(links_for_rule(links, rule)), 3)

    def test_numeric_query_ids(self) -> None:
        page = "".join(
            f'<div class="news-card"><a href="/nd.pweb?NID={i}">Haber başlığı numara {i}</a></div>'
            for i in range(101, 104)
        )
        links = collect_links(page.encode(), "https://ornek.test/nl.pweb")
        rule = deterministic_rule(links)
        self.assertEqual(len(links_for_rule(links, rule)), 3)

    def test_turkish_dates_and_titles(self) -> None:
        self.assertEqual(_parse_dt("29 Eylül 2026").date().isoformat(), "2026-09-29")
        self.assertEqual(_parse_dt("29.09.2026").date().isoformat(), "2026-09-29")
        self.assertEqual(_detail_date('<meta property="article:published_time" content="2026-09-29">').date().isoformat(),
                         "2026-09-29")
        self.assertEqual(normalize_title("İŞ-BİRLİĞİ"), normalize_title("iş birliği"))

    def test_unrelated_sidebar_text_is_rejected(self) -> None:
        self.assertFalse(_body_matches_title("Kurban Bayramı", "Cumhuriyet Bayramı kutlandı."))
        self.assertTrue(_body_matches_title("Ankara Ticaret Odası ziyareti", "Ankara Ticaret Odasında görüşme yapıldı."))


if __name__ == "__main__":
    unittest.main()
