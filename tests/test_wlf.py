"""PoC 가이드의 테스트 케이스표가 기대 결과대로 판정되는지 확인한다.  python -m unittest"""
import os
import unittest

from wlf.extract import extract_regex
from wlf.matcher import CLEAR, HIT, SUSPECT, check_draft, judge, load_watchlist, sort_for_alert
from wlf.normalize import normalize_name
from wlf.similarity import jaro_winkler

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WL = load_watchlist(os.path.join(BASE, "data", "watchlist.csv"))


def run(doc_no):
    with open(os.path.join(BASE, "data", "drafts", f"{doc_no}.txt"), encoding="utf-8") as f:
        draft = extract_regex(f.read())
    return {r.field: r for r in check_draft(draft, WL)}


class NormalizeTest(unittest.TestCase):
    def test_corp_marks_removed(self):
        for raw in ["(주)가나다무역", "주식회사 가나다무역", "㈜가나다무역", "가나다무역(주)", "가나다 무역"]:
            self.assertEqual(normalize_name(raw), "가나다무역", raw)
        self.assertEqual(normalize_name("GND Trading Co., Ltd."), "GNDTRADING")
        self.assertEqual(normalize_name("Prince Inc."), "PRINCE")

    def test_jaro_winkler(self):
        self.assertEqual(jaro_winkler("가나다무역", "가나다무역"), 1.0)
        self.assertAlmostEqual(jaro_winkler("MARTHA", "MARHTA"), 0.9611, places=4)

    def test_thresholds(self):
        self.assertEqual(judge(95), HIT)
        self.assertEqual(judge(94.9), SUSPECT)
        self.assertEqual(judge(85), SUSPECT)
        self.assertEqual(judge(84.9), CLEAR)


class CaseTableTest(unittest.TestCase):
    def test_extraction(self):
        r = run("DRAFT-2026-005")
        self.assertEqual(r["대표자명"].extracted_name, "홍길동")
        self.assertEqual(r["업체명"].extracted_name, "㈜라온식품")

    def test_exact(self):
        self.assertEqual(run("DRAFT-2026-001")["업체명"].result, HIT)

    def test_corp_mark_difference(self):
        self.assertEqual(run("DRAFT-2026-002")["업체명"].result, HIT)

    def test_spacing_and_typo(self):
        self.assertEqual(run("DRAFT-2026-003")["업체명"].result, SUSPECT)

    def test_alias(self):
        r = run("DRAFT-2026-004")["업체명"]
        self.assertEqual((r.result, r.matched_wl_id), (HIT, "WL-0005"))

    def test_same_name_different_birth(self):
        r = run("DRAFT-2026-005")["대표자명"]
        self.assertEqual((r.result, r.score), (SUSPECT, 90.0))

    def test_ceo_hit(self):
        self.assertEqual(run("DRAFT-2026-007")["대표자명"].result, HIT)

    def test_clear(self):
        for doc in ["DRAFT-2026-006", "DRAFT-2026-008"]:
            for r in run(doc).values():
                self.assertEqual(r.result, CLEAR, doc)

    def test_high_risk_first(self):
        results = [r for d in ["DRAFT-2026-003", "DRAFT-2026-005"] for r in run(d).values()]
        self.assertEqual(sort_for_alert(results)[0].risk_level, "상")


if __name__ == "__main__":
    unittest.main()
