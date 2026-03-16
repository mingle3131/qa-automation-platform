import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# → 어떤 위치에서 실행하든 analyzer 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import os
from datetime import datetime
from analyzer.db_manager import fetch_all_results, get_summary


def generate_report():
    # DB에서 전체 테스트 결과를 가져와 콘솔 리포트를 출력하고 DataFrame을 반환하는 함수

    # DB에서 전체 결과 조회
    results = fetch_all_results()

    # 저장된 결과가 없으면 안내 메시지 출력 후 종료
    if not results:
        print("저장된 테스트 결과가 없습니다.")
        return None

    # 결과 리스트를 pandas DataFrame으로 변환
    df = pd.DataFrame(results)

    # DB 통계 요약 조회 (전체/성공/실패/성공률)
    summary = get_summary()

    # 리포트 헤더 출력
    print("===== QA 테스트 분석 리포트 =====")
    print(f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"전체: {summary['total']}개 | 성공: {summary['pass']}개 | "
          f"실패: {summary['fail']}개 | 성공률: {summary['pass_rate']}%")
    print()

    # FAIL 목록 출력 (FAIL이 존재할 때만)
    fail_df = df[df["result"] == "FAIL"]
    if not fail_df.empty:
        print("[ FAIL 목록 ]")
        for _, row in fail_df.iterrows():
            # test_id, title, error_message 순으로 출력
            print(f"  [{row['test_id']}] {row['title']}")
            print(f"    오류: {row['error_message']}")
        print()

    # 최근 5건 실행 이력 출력 (test_id, title, result, executed_at 컬럼만)
    print("[ 최근 5건 실행 이력 ]")
    recent = df[["test_id", "title", "result", "executed_at"]].head(5)
    print(recent.to_string(index=False))

    return df


def save_report_csv(df):
    # DataFrame을 CSV 파일로 저장하는 함수
    # utf-8-sig 인코딩으로 저장하여 엑셀에서 한글 깨짐 방지

    # data/reports/ 폴더가 없으면 자동 생성
    report_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reports")
    os.makedirs(report_dir, exist_ok=True)

    # 타임스탬프 기반 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(report_dir, f"report_{timestamp}.csv")

    # CSV 저장 (엑셀 한글 호환: utf-8-sig, 인덱스 제외)
    df.to_csv(file_path, encoding="utf-8-sig", index=False)

    print(f"[리포트] CSV 저장 완료: {file_path}")
    return file_path


if __name__ == "__main__":
    # 리포트 생성
    df = generate_report()

    # 결과가 있을 때만 CSV 저장
    if df is not None:
        save_report_csv(df)
