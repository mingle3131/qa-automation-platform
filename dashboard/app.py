import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# → 어떤 위치에서 실행하든 analyzer 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from analyzer.db_manager import fetch_all_results, get_summary


# 페이지 기본 설정 (탭 제목, 레이아웃)
st.set_page_config(page_title="QA 자동화 대시보드", layout="wide")

# 대시보드 제목
st.title("🧪 QA 자동화 테스트 대시보드")

st.divider()

# ── 데이터 로드 ──────────────────────────────────────────
# DB에서 전체 테스트 결과 조회
results = fetch_all_results()

# 저장된 결과가 없으면 안내 메시지 출력 후 렌더링 중단
if not results:
    st.warning("저장된 테스트 결과가 없습니다.")
    st.stop()

# 결과 리스트를 DataFrame으로 변환
df = pd.DataFrame(results)

# 통계 요약 조회 (전체/성공/실패/성공률)
summary = get_summary()

# ── 상단 지표 카드 ────────────────────────────────────────
st.subheader("📊 전체 요약")

# 4개 컬럼에 지표 카드 배치
col1, col2, col3, col4 = st.columns(4)

with col1:
    # 전체 테스트 수
    st.metric(label="전체 테스트", value=f"{summary['total']}개")

with col2:
    # PASS 수
    st.metric(label="✅ PASS", value=f"{summary['pass']}개")

with col3:
    # FAIL 수
    st.metric(label="❌ FAIL", value=f"{summary['fail']}개")

with col4:
    # 성공률
    st.metric(label="성공률", value=f"{summary['pass_rate']}%")

st.divider()

# ── 중단 차트 ─────────────────────────────────────────────
chart_left, chart_right = st.columns(2)

with chart_left:
    # PASS/FAIL 비율 막대 차트
    st.subheader("PASS / FAIL 비율")

    # PASS/FAIL 카운트를 Series로 집계
    pass_fail_counts = df["result"].value_counts()
    st.bar_chart(pass_fail_counts)

with chart_right:
    # 날짜별 실행 건수 막대 차트
    st.subheader("날짜별 실행 건수")

    # executed_at 컬럼에서 날짜(YYYY-MM-DD)만 추출
    df["date"] = pd.to_datetime(df["executed_at"]).dt.date

    # 날짜별 건수 집계
    daily_counts = df.groupby("date").size().rename("실행 건수")
    st.bar_chart(daily_counts)

st.divider()

# ── 하단 전체 결과 테이블 ──────────────────────────────────
st.subheader("전체 테스트 결과")

# 전체 결과를 인터랙티브 테이블로 표시
st.dataframe(df, width='stretch')

st.divider()

# ── FAIL 목록 (FAIL이 존재할 때만 표시) ──────────────────
fail_df = df[df["result"] == "FAIL"]

if not fail_df.empty:
    st.subheader("❌ FAIL 목록")

    # FAIL인 행만 필터링하여 표시
    st.dataframe(fail_df, width='stretch')
