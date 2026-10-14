"""이름 정규화: 공백·법인 표기 제거, 영문 대문자 통일."""
import re
import unicodedata

# 긴 표기부터 지워야 "Co., Ltd." 가 "Co." 만 지워지고 남는 일이 없다.
_KR_CORP = [
    r"유한책임회사", r"주식회사", r"유한회사", r"합자회사", r"합명회사",
    r"\(주\)", r"\(유\)", r"㈜", r"㈲",
]
# 영문 표기는 단어 경계에서만 지운다 (PRINCE 의 'INC' 같은 오삭제 방지).
_EN_CORP = [
    r"co\.?\s*,?\s*ltd\.?", r"corporation", r"corp\.?", r"inc\.?",
    r"l\.?l\.?c\.?", r"limited", r"ltd\.?", r"company", r"co\.",
]
_CORP_RE = re.compile(
    "|".join(_KR_CORP + [rf"(?<![A-Za-z]){p}(?![A-Za-z])" for p in _EN_CORP]),
    re.IGNORECASE,
)
_NON_WORD_RE = re.compile(r"[^0-9A-Z가-힣]")


def normalize_name(name: str) -> str:
    """'(주) 가나다 무역' -> '가나다무역', 'GND Trading Co., Ltd.' -> 'GNDTRADING'."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name)
    # NFKC 는 ㈜ 를 (주) 로 풀어주므로 그 뒤에 법인 표기를 지운다.
    s = _CORP_RE.sub(" ", s)
    s = s.upper()
    return _NON_WORD_RE.sub("", s)


def split_alias(alias: str) -> list[str]:
    return [a.strip() for a in (alias or "").split(",") if a.strip()]
