"""요주의 리스트(WL) 대조와 점수·판정 규칙."""
import csv
from dataclasses import asdict, dataclass

from .extract import Draft
from .normalize import normalize_name, split_alias
from .similarity import jaro_winkler

HIT_THRESHOLD = 95      # 이상 -> 확정 Hit
SUSPECT_THRESHOLD = 85  # 이상 -> 의심, 미만 -> 정상
BONUS = 5               # 생년월일/설립일 또는 국가 일치
PENALTY = -10           # 불일치 (동명이인 구분용)

HIT, SUSPECT, CLEAR = "확정 Hit", "의심", "정상"
RISK_ORDER = {"상": 0, "중": 1, "하": 2}


@dataclass
class MatchResult:
    doc_no: str
    field: str            # 업체명 / 대표자명
    extracted_name: str
    matched_wl_id: str
    matched_name: str     # WL 에서 실제로 맞은 이름(본명 또는 별칭)
    risk_level: str
    list_source: str
    base_score: float
    adjust: int
    adjust_reason: str
    score: float
    result: str

    def to_dict(self) -> dict:
        return asdict(self)


def load_watchlist(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def judge(score: float) -> str:
    if score >= HIT_THRESHOLD:
        return HIT
    if score >= SUSPECT_THRESHOLD:
        return SUSPECT
    return CLEAR


def name_score(query: str, wl: dict) -> tuple[float, str]:
    """WL 한 건의 본명·영문명·별칭 중 가장 높은 점수와 그 이름."""
    q = normalize_name(query)
    if not q:
        return 0.0, ""
    best, best_name = 0.0, ""
    for cand in [wl["name_kr"], wl["name_en"], *split_alias(wl.get("alias", ""))]:
        c = normalize_name(cand)
        if not c:
            continue
        s = 100.0 if q == c else round(jaro_winkler(q, c) * 100, 1)
        if s > best:
            best, best_name = s, cand
    return best, best_name


def attribute_adjust(date: str, country: str, wl: dict) -> tuple[int, str]:
    """생년월일/설립일을 우선 비교하고, 없으면 국가를 비교한다. 비교할 값이 없으면 0점."""
    wl_date = wl.get("birth_or_est", "")
    if date and wl_date:
        return (BONUS, "일자 일치") if date == wl_date else (PENALTY, f"일자 불일치({wl_date})")
    wl_country = wl.get("country", "").upper()
    if country and wl_country:
        return (BONUS, "국가 일치") if country == wl_country else (PENALTY, f"국가 불일치({wl_country})")
    return 0, ""


def match_one(doc_no, field, name, date, country, target_type, watchlist) -> MatchResult:
    best = None
    for wl in watchlist:
        if wl["target_type"] != target_type:
            continue
        base, matched = name_score(name, wl)
        if base == 0:
            continue
        adj, reason = attribute_adjust(date, country, wl)
        score = max(0.0, min(100.0, base + adj))
        key = (score, base)
        if best is None or key > best[0]:
            best = (key, wl, matched, base, adj, reason, score)
    if best is None:
        return MatchResult(doc_no, field, name, "", "", "", "", 0.0, 0, "", 0.0, CLEAR)
    _, wl, matched, base, adj, reason, score = best
    result = judge(score)
    if result == CLEAR:
        # 정상 건은 근접 후보만 참고로 남기고 WL ID 는 비워 둔다.
        return MatchResult(doc_no, field, name, "", matched, "", "", base, adj, reason, score, CLEAR)
    return MatchResult(doc_no, field, name, wl["wl_id"], matched, wl["risk_level"],
                       wl["list_source"], base, adj, reason, score, result)


def check_draft(draft: Draft, watchlist: list[dict]) -> list[MatchResult]:
    """업체명은 법인 리스트와, 대표자명은 개인 리스트와 대조한다."""
    results = []
    if draft.company_name:
        results.append(match_one(draft.doc_no, "업체명", draft.company_name,
                                 draft.est_date, draft.country, "법인", watchlist))
    if draft.ceo_name:
        # 개인은 국적 정보가 품의서에 없으므로 생년월일만 비교한다.
        results.append(match_one(draft.doc_no, "대표자명", draft.ceo_name,
                                 draft.ceo_birth, "", "개인", watchlist))
    return results


def needs_alert(results: list[MatchResult]) -> bool:
    return any(r.result in (HIT, SUSPECT) for r in results)


def sort_for_alert(results: list[MatchResult]) -> list[MatchResult]:
    """위험등급 '상' 최상단, 그다음 판정(Hit>의심>정상), 점수 내림차순. 정상 건은 등급이 없어 맨 아래."""
    result_order = {HIT: 0, SUSPECT: 1, CLEAR: 2}
    return sorted(results, key=lambda r: (RISK_ORDER.get(r.risk_level, 9),
                                          result_order[r.result], -r.score))
