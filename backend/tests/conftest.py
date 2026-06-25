"""pytest 공통 설정 — backend/ 를 import 루트로 사용.

테스트는 `cd backend && python -m pytest` 로 실행한다.
모듈은 운영 코드와 동일하게 `services.*`, `main` 으로 import 한다.
"""
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
