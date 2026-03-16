import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
# → pytest 실행 시 어느 위치에서 실행하든 프로젝트 내 모듈을 정상적으로 import할 수 있도록 설정
sys.path.insert(0, os.path.dirname(__file__))
