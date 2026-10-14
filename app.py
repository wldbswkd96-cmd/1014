"""AML WLF 자동 검증 PoC 화면.  실행: streamlit run app.py

흐름: 품의서 업로드 → 추출 결과 확인 → 매칭 결과표 → 알림
"""
import glob
import os

import pandas as pd
import streamlit as st

from wlf.extract import ai_available, extract
from wlf.log import append_results, mark_reviewed, read_log
from wlf.matcher import (CLEAR, HIT, HIT_THRESHOLD, SUSPECT, SUSPECT_THRESHOLD,
                         check_draft, load_watchlist, sort_for_alert)

BASE = os.path.dirname(os.path.abspath(__file__))
WL_PATH = os.path.join(BASE, "data", "watchlist.csv")
LOG_PATH = os.path.join(BASE, "data", "check_log.csv")
SAMPLE_DIR = os.path.join(BASE, "data", "drafts")

RISK_COLOR = {"상": "#f8d7da", "중": "#fff3cd", "하": "#d1e7dd"}
RESULT_COLOR = {HIT: "#dc3545", SUSPECT: "#fd7e14", CLEAR: "#198754"}

st.set_page_config(page_title="AML WLF 검증 PoC", page_icon="🛡️", layout="wide")
st.title("🛡️ AML 요주의 인물/법인 WLF 자동 검증 (PoC)")
st.caption("※ 교육용 가상 데이터만 사용합니다. 실제 AML 시스템과 연동되지 않습니다.")


@st.cache_data
def watchlist() -> list[dict]:
    return load_watchlist(WL_PATH)


def color_rows(row: pd.Series) -> list[str]:
    bg = RISK_COLOR.get(row.get("위험등급", ""), "")
    return [f"background-color: {bg}" if bg else ""] * len(row)


def color_result(v: str) -> str:
    return f"color: {RESULT_COLOR.get(v, '')}; font-weight: bold"


tab_check, tab_wl, tab_log = st.tabs(["① 품의서 검증", "② 요주의 리스트 조회 (모의 연동)", "③ 검증 이력"])

# ---------------------------------------------------------------- ① 품의서 검증
with tab_check:
    left, right = st.columns([2, 1])
    with left:
        uploads = st.file_uploader("품의서 업로드 (.txt)", type=["txt"], accept_multiple_files=True)
        samples = sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.txt")))
        picked = st.multiselect("또는 샘플 품의서 선택", [os.path.basename(p) for p in samples])
    with right:
        use_ai = st.toggle("AI(Claude) 추출 사용", value=False, disabled=not ai_available(),
                           help="ANTHROPIC_API_KEY 가 설정된 경우에만 사용 가능. 실패 시 정규식으로 대체.")
        save_log = st.checkbox("검증 결과를 로그에 저장", value=True)
        st.markdown(f"**판정 기준**  \n{HIT_THRESHOLD}점 이상 → 확정 Hit  \n"
                    f"{SUSPECT_THRESHOLD}~{HIT_THRESHOLD - 1}점 → 의심  \n{SUSPECT_THRESHOLD}점 미만 → 정상")

    docs = [(u.name, u.getvalue().decode("utf-8", errors="replace")) for u in uploads or []]
    for name in picked:
        with open(os.path.join(SAMPLE_DIR, name), encoding="utf-8") as f:
            docs.append((name, f.read()))

    if st.button("🔍 검증 실행", type="primary", disabled=not docs):
        drafts, results = [], []
        with st.spinner("추출 및 대조 중..."):
            for _, text in docs:
                d = extract(text, use_ai=use_ai)
                drafts.append(d)
                results += check_draft(d, watchlist())
        if save_log:
            append_results(LOG_PATH, results)
        st.session_state["drafts"], st.session_state["results"] = drafts, results

    if "results" in st.session_state:
        drafts, results = st.session_state["drafts"], st.session_state["results"]

        alerts = [r for r in sort_for_alert(results) if r.result != CLEAR]
        st.subheader("🚨 알림")
        if not alerts:
            st.success("요주의 리스트와 매칭된 건이 없습니다.")
        for r in alerts:
            msg = (f"**[{r.risk_level}] {r.result}** — {r.doc_no} {r.field} "
                   f"'{r.extracted_name}' ↔ {r.matched_wl_id} '{r.matched_name}' "
                   f"({r.list_source}, {r.score:.1f}점)")
            (st.error if r.result == HIT else st.warning)(msg)

        st.subheader("1. 추출 결과 확인")
        st.dataframe(pd.DataFrame([{
            "문서번호": d.doc_no, "접수일": d.recv_date, "부서": d.dept, "구분": d.contract_type,
            "업체명": d.company_name, "대표자": d.ceo_name, "대표자 생년월일": d.ceo_birth,
            "설립일": d.est_date, "국가": d.country, "사업자번호": d.biz_no,
            "금액": d.amount, "추출방식": d.extract_method,
        } for d in drafts]), hide_index=True, use_container_width=True)

        st.subheader("2. 매칭 결과표")
        df = pd.DataFrame([{
            "문서번호": r.doc_no, "구분": r.field, "추출명": r.extracted_name,
            "WL ID": r.matched_wl_id, "매칭명(본명/별칭)": r.matched_name,
            "위험등급": r.risk_level, "출처": r.list_source, "이름점수": r.base_score,
            "가감": r.adjust, "가감사유": r.adjust_reason, "최종점수": r.score, "판정": r.result,
        } for r in sort_for_alert(results)])
        st.dataframe(df.style.apply(color_rows, axis=1).map(color_result, subset=["판정"])
                     .format({"이름점수": "{:.1f}", "최종점수": "{:.1f}"}),
                     hide_index=True, use_container_width=True)

        with st.expander("품의서 원문 보기"):
            for d in drafts:
                st.text_area(d.doc_no or "(문서번호 없음)", d.body_text, height=200, disabled=True)

# ---------------------------------------------------------------- ② WL 조회
with tab_wl:
    wl_df = pd.DataFrame(watchlist())
    c1, c2, c3 = st.columns([2, 1, 1])
    q = c1.text_input("이름/별칭 검색", placeholder="예: 가나다, GND")
    types = c2.multiselect("대상 구분", ["개인", "법인"], default=["개인", "법인"])
    risks = c3.multiselect("위험등급", ["상", "중", "하"], default=["상", "중", "하"])
    view = wl_df[wl_df["target_type"].isin(types) & wl_df["risk_level"].isin(risks)]
    if q:
        hay = (view["name_kr"] + "|" + view["name_en"] + "|" + view["alias"]).str.upper()
        view = view[hay.str.contains(q.strip().upper(), regex=False)]
    st.caption(f"{len(view)} / {len(wl_df)}건")
    st.dataframe(view.rename(columns={"risk_level": "위험등급"}).style.apply(color_rows, axis=1),
                 hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- ③ 검증 이력
with tab_log:
    rows = read_log(LOG_PATH)
    if not rows:
        st.info("아직 검증 이력이 없습니다.")
    else:
        log_df = pd.DataFrame(rows).iloc[::-1]
        only_open = st.checkbox("미확인 위험건만 보기 (확정 Hit/의심 중 담당자 미확인)")
        if only_open:
            log_df = log_df[(log_df["result"] != CLEAR) & (~log_df["reviewed"])]
        edited = st.data_editor(
            log_df, hide_index=True, use_container_width=True,
            disabled=[c for c in log_df.columns if c != "reviewed"],
            column_config={"reviewed": st.column_config.CheckboxColumn("담당자 확인")},
            key="log_editor",
        )
        newly = set(edited.loc[edited["reviewed"] & ~log_df["reviewed"], "check_id"])
        if st.button("✅ 확인 완료 저장", disabled=not newly):
            mark_reviewed(LOG_PATH, newly)
            st.success(f"{len(newly)}건 확인 완료 처리했습니다.")
            st.rerun()
