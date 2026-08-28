"""앱 부팅 스모크 — 테스트가 초록인데 앱이 안 뜨는 상황을 막는다.

2026-08-27: `mcp` 가 out-of-band 로 올라가며 `sse-starlette>=1.6.1` →
`starlette 1.6.0` 을 끌고 왔고, `fastapi==0.115.5`(starlette<0.42)와 충돌해
`main` import 자체가 죽었다. 그런데 **테스트 340건은 전부 통과했다** —
`main` 을 import 하는 테스트가 하나도 없었기 때문이다. CI 초록 + 앱 사망.

이 파일은 그 구멍만 막는다. 라우팅·응답 검증은 각 모듈 테스트가 한다.
"""
from __future__ import annotations

import importlib

import pytest


def test_main_imports():
    """main 이 import 되는가 — 의존성 버전 충돌은 여기서 잡힌다."""
    main = importlib.import_module("main")
    assert main.app is not None


def test_core_routes_registered():
    """핵심 라우트가 실제로 등록됐는가.

    모듈 테스트가 다 통과해도 라우터 배선이 빠지면 앱은 빈 껍데기다.
    """
    main = importlib.import_module("main")
    inner = getattr(main.app, "_app", main.app)   # /mcp 마운트 래퍼를 벗긴다
    paths = {r.path for r in inner.routes if hasattr(r, "path")}
    for p in ("/health", "/api/diagnose", "/api/feasibility/run",
              "/api/feasibility/briefs"):
        assert p in paths, f"라우트 누락: {p}"


def test_feasibility_request_accepts_limits_determined_by():
    """스키마가 실제 앱에서 심의 플래그를 받는가(계약 회귀)."""
    schemas = importlib.import_module("schemas")
    req = schemas.FeasibilityRequest(
        address="서울특별시 영등포구 당산동3가 385",
        facility_use="업무시설",
        limits_determined_by="심의",
    )
    assert req.limits_determined_by == "심의"
    with pytest.raises(Exception):
        schemas.FeasibilityRequest(
            address="a", facility_use="업무시설", limits_determined_by="협의",
        )
