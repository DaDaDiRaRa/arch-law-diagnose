"""법규 변경 자동 스캔 스케줄러 (APScheduler).

- 시작 시 AsyncIOScheduler 기동
- 환경변수로 ON/OFF + cron 표현식 변경 가능
  - ENABLE_LAW_CHANGE_CRON=true|false (기본 true)
  - LAW_CHANGE_CRON='m h dom mon dow' 형식 (기본 '0 3 * * 0' = 매주 일요일 03:00 KST)
- 스캔 대상: 17개 시도 도시계획조례 (시군구는 fetch_ordinance 매칭 한계로 1차에서 제외)
- 변경 감지 시 ordinance_versions 에 새 해시 누적 → 프론트 LawChangeAlert 가 표시
"""
from __future__ import annotations

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.law_change_tracker import LawChangeTracker

logger = logging.getLogger(__name__)

DEFAULT_CRON = "0 3 * * 0"  # 매주 일요일 03:00 KST
DEFAULT_TZ = "Asia/Seoul"

# 17개 시도 — seed_ordinances.py 와 동일 목록
SIDO_TARGETS: list[tuple[str, str]] = [
    ("11000", "서울특별시"),
    ("26000", "부산광역시"),
    ("27000", "대구광역시"),
    ("28000", "인천광역시"),
    ("29000", "광주광역시"),
    ("30000", "대전광역시"),
    ("31000", "울산광역시"),
    ("36000", "세종특별자치시"),
    ("41000", "경기도"),
    ("42000", "강원특별자치도"),
    ("43000", "충청북도"),
    ("44000", "충청남도"),
    ("45000", "전북특별자치도"),
    ("46000", "전라남도"),
    ("47000", "경상북도"),
    ("48000", "경상남도"),
    ("50000", "제주특별자치도"),
]


async def scan_all_sido(tracker: LawChangeTracker) -> dict:
    """17개 시도 도시계획조례 일괄 스캔 → 변경 감지 통계."""
    changed: list[dict] = []
    failed: list[dict] = []
    scanned = 0
    for code, name in SIDO_TARGETS:
        try:
            res = await tracker.scan(code, name, "도시계획 조례")
        except Exception as e:
            logger.error("law_change scan 실패 (%s %s): %s", code, name, e)
            failed.append({"code": code, "name": name, "error": str(e)})
            continue
        scanned += 1
        if res.get("changed"):
            changed.append(res)
            logger.warning(
                "🔔 법규 변경 감지: %s %s (prev=%s → curr=%s)",
                code, name, res.get("previous_hash"), res.get("current_hash"),
            )
        # 법제처 API 레이트 리밋 배려
        await asyncio.sleep(0.5)

    summary = {
        "scanned": scanned,
        "changed_count": len(changed),
        "failed_count": len(failed),
        "changed": changed,
        "failed": failed,
    }
    logger.info(
        "법규 일괄 스캔 완료: %d/%d 곳, 변경 %d건, 실패 %d건",
        scanned, len(SIDO_TARGETS), len(changed), len(failed),
    )
    return summary


def start_scheduler(tracker: LawChangeTracker) -> AsyncIOScheduler | None:
    """ENABLE_LAW_CHANGE_CRON=true 일 때 스케줄러 시작.

    Returns:
      AsyncIOScheduler 인스턴스 (비활성 시 None)
    """
    enabled = (os.getenv("ENABLE_LAW_CHANGE_CRON", "true").lower() == "true")
    if not enabled:
        logger.info("법규 변경 cron 비활성 (ENABLE_LAW_CHANGE_CRON=false)")
        return None

    cron_expr = os.getenv("LAW_CHANGE_CRON", DEFAULT_CRON).strip()
    tz = os.getenv("LAW_CHANGE_TZ", DEFAULT_TZ).strip()

    scheduler = AsyncIOScheduler(timezone=tz)
    try:
        trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
    except Exception as e:
        logger.error("LAW_CHANGE_CRON 표현식 오류 '%s' (%s) — 기본값 사용", cron_expr, e)
        trigger = CronTrigger.from_crontab(DEFAULT_CRON, timezone=tz)
        cron_expr = DEFAULT_CRON

    scheduler.add_job(
        scan_all_sido,
        trigger=trigger,
        args=[tracker],
        id="law_change_scan",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,  # 서버 다운 등으로 놓친 실행, 1시간 안이면 늦게라도 1회 실행
    )
    scheduler.start()
    logger.info("법규 변경 cron 시작: '%s' (%s) — 다음 실행: %s",
                cron_expr, tz,
                scheduler.get_job("law_change_scan").next_run_time)
    return scheduler
