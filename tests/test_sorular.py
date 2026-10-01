import json
import unittest
from pathlib import Path

from katki.sorular import BOLGE_ILLERI, BOLGE_SORUSU, GENEL_KAPSAMLAR, IL_BOLGESI, il_sorusu

GEOJSON = Path(__file__).resolve().parent.parent / "katki" / "static" / "tr-iller.json"


class SorularTests(unittest.TestCase):
    def test_81_il_tek_bolgede(self) -> None:
        iller = [il for iller in BOLGE_ILLERI.values() for il in iller]
        self.assertEqual(len(iller), 81)
        self.assertEqual(len(set(iller)), 81)

    def test_bolge_sorusu_secenekleri(self) -> None:
        secenekler = set(BOLGE_SORUSU["bolge"]["criteria"])
        self.assertEqual(secenekler, set(BOLGE_ILLERI) | set(GENEL_KAPSAMLAR))

    def test_il_sorusu_yalniz_o_bolgenin_illeri(self) -> None:
        for bolge, iller in BOLGE_ILLERI.items():
            self.assertEqual(list(il_sorusu(bolge)["il"]["criteria"]), iller)

    def test_harita_adlari_il_listesiyle_ayni(self) -> None:
        adlar = {f["properties"]["name"] for f in json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]}
        self.assertEqual(adlar, set(IL_BOLGESI))


if __name__ == "__main__":
    unittest.main()
