import sys
import os

# 프로젝트 루트를 Python 경로에 추가
# → 어떤 위치에서 실행하든 프로젝트 내 모듈을 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from datetime import datetime


# DB 파일 경로: 프로젝트 루트/data/qa_results.db
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "qa_results.db")


def get_connection():
    # data/ 폴더가 없으면 자동 생성
    data_dir = os.path.dirname(DB_PATH)
    os.makedirs(data_dir, exist_ok=True)

    # SQLite DB에 연결 후 conn 반환
    conn = sqlite3.connect(DB_PATH)
    return conn


def create_tables():
    # test_results 테이블 생성 (이미 존재하면 생략)
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id           TEXT NOT NULL,
            title             TEXT,
            result            TEXT NOT NULL,
            screenshot_path   TEXT,
            error_message     TEXT,
            executed_at       TEXT,
            run_id            TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] test_results 테이블 생성 완료 (또는 이미 존재)")


def save_result(test_id, title, result, screenshot_path=None, error_message=None, run_id=None):
    # 현재 실행 일시 기록
    executed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()

    # SQL 인젝션 방지를 위해 플레이스홀더(?) 방식으로 INSERT
    conn.execute(
        """
        INSERT INTO test_results
            (test_id, title, result, screenshot_path, error_message, executed_at, run_id)
        VALUES
            (?, ?, ?, ?, ?, ?, ?)
        """,
        (test_id, title, result, screenshot_path, error_message, executed_at, run_id),
    )

    conn.commit()
    conn.close()


def fetch_all_results():
    conn = get_connection()

    # Row 객체를 dict처럼 접근할 수 있도록 row_factory 설정
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        "SELECT * FROM test_results ORDER BY executed_at DESC"
    )
    rows = cursor.fetchall()

    # sqlite3.Row → dict 변환 후 리스트로 반환
    results = [dict(row) for row in rows]
    conn.close()
    return results


def get_summary(run_id: str = None):
    conn = get_connection()

    if run_id:
        # 특정 run_id의 결과만 집계 (누적 방지)
        total = conn.execute(
            "SELECT COUNT(*) FROM test_results WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        passed = conn.execute(
            "SELECT COUNT(*) FROM test_results WHERE result = 'PASS' AND run_id = ?", (run_id,)
        ).fetchone()[0]
    else:
        # run_id 미지정 시 전체 레코드 집계
        total = conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        passed = conn.execute(
            "SELECT COUNT(*) FROM test_results WHERE result = 'PASS'"
        ).fetchone()[0]

    conn.close()

    failed = total - passed

    # 전체 건수가 0이면 pass_rate는 0.0으로 처리
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0.0

    return {"total": total, "pass": passed, "fail": failed, "pass_rate": pass_rate}


if __name__ == "__main__":
    # 테이블 초기화
    create_tables()

    # 현재 DB 요약 통계 출력
    summary = get_summary()
    print(f"[요약] 전체: {summary['total']}개 | "
          f"성공: {summary['pass']}개 | "
          f"실패: {summary['fail']}개 | "
          f"성공률: {summary['pass_rate']}%")
