"""품의서 텍스트에서 업체명·대표자명 등을 추출한다.

기본은 AI(Claude) 추출이고, API 키가 없거나 실패하면 정규식으로 보조한다.
"""
import os
import re
from dataclasses import asdict, dataclass

DATE = r"(\d{4})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})"


@dataclass
class Draft:
    doc_no: str = ""
    recv_date: str = ""
    dept: str = ""
    contract_type: str = ""
    company_name: str = ""
    ceo_name: str = ""
    ceo_birth: str = ""
    est_date: str = ""
    country: str = ""
    biz_no: str = ""
    amount: int | None = None
    body_text: str = ""
    extract_method: str = "regex"

    def to_dict(self) -> dict:
        return asdict(self)


def _field(text: str, *labels: str) -> str:
    for label in labels:
        m = re.search(rf"^\s*[-·•]?\s*{label}\s*[:：]\s*(.+?)\s*$", text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def _date(value: str) -> str:
    m = re.search(DATE, value or "")
    if not m:
        return ""
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def extract_regex(text: str) -> Draft:
    ceo_raw = _field(text, "대표자", "대표이사", "대표자명", "대표")
    # "홍길동 (1980-07-15)" 처럼 괄호 안에 생년월일이 붙어 오는 경우
    ceo_name = re.sub(r"\(.*?\)", "", ceo_raw).strip()
    amount_raw = _field(text, "계약금액", "금액")
    digits = re.sub(r"[^\d]", "", amount_raw)
    return Draft(
        doc_no=_field(text, "문서번호", "품의번호"),
        recv_date=_date(_field(text, "접수일", "기안일")),
        dept=_field(text, "기안부서", "부서"),
        contract_type=_field(text, "계약구분"),
        company_name=_field(text, "계약업체", "계약업체명", "업체명", "거래처"),
        ceo_name=ceo_name,
        ceo_birth=_date(_field(text, "생년월일") or ceo_raw),
        est_date=_date(_field(text, "설립일", "설립일자")),
        country=_field(text, "국가", "국적").upper(),
        biz_no=_field(text, "사업자등록번호", "사업자번호"),
        amount=int(digits) if digits else None,
        body_text=text,
        extract_method="regex",
    )


def extract_ai(text: str) -> Draft:
    """Claude 로 추출. 정규식 결과를 기본값으로 두고 AI 가 찾은 값으로 덮어쓴다."""
    import anthropic
    from pydantic import BaseModel

    class Extracted(BaseModel):
        company_name: str
        ceo_name: str
        ceo_birth: str
        est_date: str
        country: str

    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": (
                "다음 계약 품의서에서 계약업체명(company_name), 대표자 성명(ceo_name), "
                "대표자 생년월일(ceo_birth), 업체 설립일(est_date), 국가코드 2자리(country)를 추출해줘. "
                "업체명은 문서에 적힌 그대로(법인 표기 포함) 쓰고, 날짜는 YYYY-MM-DD, "
                "없는 값은 빈 문자열로 둬.\n\n<document>\n" + text + "\n</document>"
            ),
        }],
        output_format=Extracted,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"AI 추출 실패 (stop_reason={response.stop_reason})")
    out = response.parsed_output
    draft = extract_regex(text)
    draft.company_name = out.company_name or draft.company_name
    draft.ceo_name = out.ceo_name or draft.ceo_name
    draft.ceo_birth = _date(out.ceo_birth) or draft.ceo_birth
    draft.est_date = _date(out.est_date) or draft.est_date
    draft.country = (out.country or draft.country).upper()
    draft.extract_method = "ai"
    return draft


def ai_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def extract(text: str, use_ai: bool = False) -> Draft:
    if use_ai:
        try:
            return extract_ai(text)
        except Exception as e:  # PoC: 어떤 이유로든 실패하면 정규식으로 대체
            draft = extract_regex(text)
            draft.extract_method = f"regex (AI 실패: {type(e).__name__})"
            return draft
    return extract_regex(text)
