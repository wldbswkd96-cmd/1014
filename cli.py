"""터미널 데모: python cli.py [품의서.txt ...]  (인자 없으면 data/drafts/*.txt 전체)"""
import argparse
import glob
import os

from wlf.extract import ai_available, extract
from wlf.log import append_results
from wlf.matcher import CLEAR, check_draft, load_watchlist, needs_alert, sort_for_alert

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="품의서 WLF 검증")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--wl", default=os.path.join(BASE, "data", "watchlist.csv"))
    ap.add_argument("--log", default=os.path.join(BASE, "data", "check_log.csv"))
    ap.add_argument("--ai", action="store_true", help="Claude 로 추출 (ANTHROPIC_API_KEY 필요)")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    files = args.files or sorted(glob.glob(os.path.join(BASE, "data", "drafts", "*.txt")))
    watchlist = load_watchlist(args.wl)
    use_ai = args.ai and ai_available()
    all_results = []

    for path in files:
        with open(path, encoding="utf-8") as f:
            draft = extract(f.read(), use_ai=use_ai)
        results = check_draft(draft, watchlist)
        all_results += results
        flag = "🚨 알림" if needs_alert(results) else "✅ 정상"
        print(f"\n[{draft.doc_no}] {flag}  (추출: {draft.extract_method})")
        for r in results:
            wl = f"{r.matched_wl_id} '{r.matched_name}' 등급:{r.risk_level} 출처:{r.list_source}" \
                if r.result != CLEAR else (f"근접 후보 '{r.matched_name}'" if r.matched_name else "후보 없음")
            adj = f" {r.adjust:+d}({r.adjust_reason})" if r.adjust else ""
            print(f"  - {r.field:4} {r.extracted_name:<24} {r.base_score:5.1f}{adj} → {r.score:5.1f}  "
                  f"{r.result:5}  {wl}")

    alerts = [r for r in sort_for_alert(all_results) if r.result != CLEAR]
    print(f"\n=== 알림 목록 ({len(alerts)}건, 위험등급 '상' 우선) ===")
    for r in alerts:
        print(f"  [{r.risk_level}] {r.result:5} {r.doc_no} {r.field} '{r.extracted_name}' "
              f"↔ {r.matched_wl_id} '{r.matched_name}' ({r.score:.1f})")

    if not args.no_log:
        append_results(args.log, all_results)
        print(f"\n로그 저장: {args.log}")


if __name__ == "__main__":
    main()
