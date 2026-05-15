"""도시별 순차 seed_ordinances 실행 (각 도시 5분 타임아웃, hang 시 다음 도시).

서울은 ordinance_seed.json 으로 이미 적재되어 있어 제외.
실행:  python _seed_loop.py
로그:  seed_logs/{city}.log
"""
import subprocess
import sys
import time
from pathlib import Path

CITIES = [
    "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시",
    "경기도", "강원특별자치도", "충청북도", "충청남도",
    "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
]

TIMEOUT_SEC = 300  # 5분
LOG_DIR = Path("seed_logs")
LOG_DIR.mkdir(exist_ok=True)

PY = Path("backend/.venv/Scripts/python.exe").resolve()

results = []
for city in CITIES:
    start = time.time()
    log_path = LOG_DIR / f"{city}.log"
    print(f"\n=== [{city}] 시작 ===", flush=True)

    with open(log_path, "w", encoding="utf-8") as logf:
        try:
            proc = subprocess.Popen(
                [str(PY), "-m", "scripts.seed_ordinances", "--commit", "--city", city],
                cwd="backend",
                stdout=logf,
                stderr=subprocess.STDOUT,
                env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ},
            )
            try:
                rc = proc.wait(timeout=TIMEOUT_SEC)
                elapsed = time.time() - start
                status = "OK" if rc == 0 else f"FAIL({rc})"
                print(f"  ✓ {status} — {elapsed:.0f}초", flush=True)
                results.append((city, status, int(elapsed)))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
                elapsed = time.time() - start
                print(f"  ⏱  TIMEOUT — {elapsed:.0f}초", flush=True)
                results.append((city, "TIMEOUT", int(elapsed)))
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ✗ ERROR: {e}", flush=True)
            results.append((city, f"ERROR:{e}", int(elapsed)))

print("\n=== 전체 결과 ===", flush=True)
print(f"{'도시':<14} {'상태':<10} {'초':>5}")
print("-" * 32)
for city, status, sec in results:
    print(f"{city:<14} {status:<10} {sec:>5}")

ok = sum(1 for _, s, _ in results if s == "OK")
fail = sum(1 for _, s, _ in results if s != "OK")
print(f"\nOK: {ok} / FAIL: {fail} / 전체: {len(results)}")
