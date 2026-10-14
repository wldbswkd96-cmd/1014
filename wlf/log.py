"""검증 결과 로그 (CSV). 컬럼은 PoC 가이드의 ③ 검증 결과 로그 정의를 따른다."""
import csv
import os
from datetime import datetime

from .matcher import MatchResult

LOG_COLUMNS = ["check_id", "doc_no", "extracted_name", "matched_wl_id", "score",
               "result", "reviewed", "checked_at"]


def append_results(path: str, results: list[MatchResult]) -> list[dict]:
    now = datetime.now()
    stamp = now.strftime("%Y%m%d%H%M%S%f")[:-3]  # 밀리초까지
    rows = [{
        "check_id": f"CHK-{stamp}-{i:02d}",
        "doc_no": r.doc_no,
        "extracted_name": r.extracted_name,
        "matched_wl_id": r.matched_wl_id,
        "score": r.score,
        "result": r.result,
        "reviewed": False,
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    } for i, r in enumerate(results, 1)]
    new_file = not os.path.exists(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if new_file:
            w.writeheader()
        w.writerows(rows)
    return rows


def read_log(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["reviewed"] = r["reviewed"] == "True"
        r["score"] = float(r["score"])
    return rows


def mark_reviewed(path: str, check_ids: set[str]) -> None:
    rows = read_log(path)
    for r in rows:
        if r["check_id"] in check_ids:
            r["reviewed"] = True
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        w.writeheader()
        w.writerows(rows)
