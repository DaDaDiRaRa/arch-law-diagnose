"""시니어 검토 요청 알림 — Slack Webhook + 로컬 로그 fallback.

환경변수:
  - SLACK_WEBHOOK_URL: Slack Incoming Webhook URL (선택)
  - REVIEW_LOG_PATH:   로컬 로그 파일 경로 (기본 ./data/review_requests.log)

웹훅 미설정 시 로컬 로그에만 기록 → 운영 환경에서 점진적 도입 가능.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ReviewNotifier:
    def __init__(self) -> None:
        self._webhook = os.getenv("SLACK_WEBHOOK_URL", "").strip()
        log_path = os.getenv("REVIEW_LOG_PATH", "./data/review_requests.log")
        self._log_path = Path(log_path).resolve()
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._http = httpx.AsyncClient(timeout=10)

    async def close(self) -> None:
        await self._http.aclose()

    @property
    def slack_configured(self) -> bool:
        return bool(self._webhook)

    async def request_review(
        self,
        *,
        requester: str | None,
        address: str,
        risk_category: str,
        risk_reason: str,
        building_info: dict | None = None,
        signal: str | None = None,
        overall_score: float | None = None,
        note: str | None = None,
    ) -> dict:
        """검토 요청 발송. Slack 시도 → 실패하든 성공하든 로컬 로그 항상 기록."""
        record = {
            "requested_at": datetime.utcnow().isoformat(),
            "requester": requester or "익명",
            "address": address,
            "risk_category": risk_category,
            "risk_reason": risk_reason,
            "signal": signal,
            "overall_score": overall_score,
            "building_info": building_info or {},
            "note": note,
        }

        self._append_log(record)

        slack_status: dict = {"sent": False, "configured": self.slack_configured}
        if self._webhook:
            slack_status = await self._post_slack(record)

        return {
            "success": True,
            "channel": "slack" if slack_status.get("sent") else "log",
            "slack": slack_status,
            "log_path": str(self._log_path),
            "preview": _short_preview(record),
        }

    def _append_log(self, record: dict) -> None:
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("리뷰 로그 기록 실패: %s", e)

    async def _post_slack(self, record: dict) -> dict:
        try:
            payload = {"text": _format_slack(record), "blocks": _format_slack_blocks(record)}
            r = await self._http.post(self._webhook, json=payload)
            ok = r.status_code == 200
            if not ok:
                logger.warning("Slack webhook 응답 비정상: %s %s", r.status_code, r.text[:200])
            return {"sent": ok, "status_code": r.status_code, "configured": True}
        except Exception as e:
            logger.warning("Slack webhook 호출 실패: %s", e)
            return {"sent": False, "error": str(e), "configured": True}


def _format_slack(r: dict) -> str:
    return (
        f"[시니어 검토 요청] {r['risk_category']} 위험\n"
        f"주소: {r['address']}\n"
        f"사유: {r['risk_reason']}\n"
        f"요청자: {r['requester']}"
    )


def _format_slack_blocks(r: dict) -> list[dict]:
    bi = r.get("building_info") or {}
    bi_text = " · ".join(f"{k}: {v}" for k, v in bi.items() if v) or "(정보 없음)"
    score_line = (
        f"종합 점수 {r.get('overall_score')}/10 · 신호 {r.get('signal') or '-'}"
        if r.get("overall_score") is not None else "(점수 미확인)"
    )
    fields = [
        {"type": "mrkdwn", "text": f"*주소*\n{r['address']}"},
        {"type": "mrkdwn", "text": f"*요청자*\n{r['requester']}"},
        {"type": "mrkdwn", "text": f"*위험 카테고리*\n{r['risk_category']}"},
        {"type": "mrkdwn", "text": f"*진단 요약*\n{score_line}"},
    ]
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🛎️ arch-law-diagnose · 시니어 검토 요청"},
        },
        {"type": "section", "fields": fields},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*위험 내용*\n{r['risk_reason']}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"건물: {bi_text}"}]},
    ]
    if r.get("note"):
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*추가 메모*\n{r['note']}"}}
        )
    return blocks


def _short_preview(r: dict) -> str:
    return f"[{r['risk_category']}] {r['risk_reason'][:80]}"
