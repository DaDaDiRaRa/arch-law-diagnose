"""LurisClient 오프라인 모킹 테스트 (respx).

LURIS 는 EUC-KR 인코딩 XML 을 반환하므로 응답을 bytes 로 구성해야 한다.
공공데이터포털 서비스 에러 봉투(OpenAPI_ServiceResponse)도 별도 검증한다.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from services.luris_client import LurisClient

LURIS_BASE = "https://apis.data.go.kr/1613000/arLandUseInfoService"


# ─── 공통 픽스처 ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _luris_env(monkeypatch):
    monkeypatch.setenv("LURIS_API_KEY", "test-key")


# ─── EUC-KR 응답 빌더 ────────────────────────────────────────────────────────

def _euckr_resp(xml_str: str) -> httpx.Response:
    """EUC-KR 인코딩 XML 응답. LurisClient 는 r.content.decode('euc-kr') 사용."""
    content = xml_str.encode("euc-kr", errors="replace")
    return httpx.Response(200, content=content)


# ─── search_action ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_action_success():
    xml = """<?xml version="1.0" encoding="EUC-KR"?>
    <response>
      <body>
        <items>
          <item><LUN_NM>공장</LUN_NM><LUN_CD>03666</LUN_CD></item>
          <item><LUN_NM>금은세공업 공장</LUN_NM><LUN_CD>02079</LUN_CD></item>
        </items>
      </body>
    </response>
    """
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTsearchLunCd").mock(return_value=_euckr_resp(xml))
        client = LurisClient()
        result = await client.search_action("공장")
        await client.close()

    assert len(result) == 2
    assert result[0]["name"] == "공장"
    assert result[0]["code"] == "03666"
    assert result[1]["name"] == "금은세공업 공장"


@pytest.mark.asyncio
async def test_search_action_no_key(monkeypatch):
    """API 키 없으면 HTTP 호출 없이 [] 반환."""
    monkeypatch.delenv("LURIS_API_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_API_KEY", raising=False)
    async with respx.mock:
        client = LurisClient()
        result = await client.search_action("공장")
        call_count = respx.calls.call_count
        await client.close()

    assert result == []
    assert call_count == 0


@pytest.mark.asyncio
async def test_search_action_empty():
    xml = "<response><body><items></items></body></response>"
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTsearchLunCd").mock(return_value=_euckr_resp(xml))
        client = LurisClient()
        result = await client.search_action("없는행위")
        await client.close()

    assert result == []


# ─── get_act_info ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_act_info_allowed():
    """단독주택 건축 가능 → ALLOWED verdict."""
    xml = """<?xml version="1.0" encoding="EUC-KR"?>
    <response>
      <body>
        <items>
          <item>
            <UNAME>자연녹지지역</UNAME>
            <UCODE>UQA430</UCODE>
            <UCODE_REF_LAW_CD>13000</UCODE_REF_LAW_CD>
            <actRegList>
              <ACT_NM>건축</ACT_NM>
              <REG_NM>가능</REG_NM>
              <luInfoList>
                <NODE_DESC>단독주택</NODE_DESC>
                <LU_REF_LAW_NM1>국토의 계획 및 이용에 관한 법률</LU_REF_LAW_NM1>
                <LU_REF_LAW_NM2></LU_REF_LAW_NM2>
                <LU_REF_LAW_NM3></LU_REF_LAW_NM3>
                <DEF_REF></DEF_REF>
              </luInfoList>
            </actRegList>
          </item>
        </items>
      </body>
    </response>
    """
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTarLandUseInfo").mock(return_value=_euckr_resp(xml))
        client = LurisClient()
        result = await client.get_act_info("11215", "UQA430", "단독주택")
        await client.close()

    assert result is not None
    assert result["zone_name"] == "자연녹지지역"
    assert result["zone_code"] == "UQA430"
    assert result["summary"]["verdict"] == "ALLOWED"
    assert result["summary"]["allowed_count"] >= 1
    assert result["summary"]["has_real_data"] is True
    assert result["acts"][0]["name"] == "건축"


@pytest.mark.asyncio
async def test_get_act_info_forbidden():
    """금지 행위 → FORBIDDEN verdict."""
    xml = """<?xml version="1.0" encoding="EUC-KR"?>
    <response>
      <body>
        <items>
          <item>
            <UNAME>보전녹지지역</UNAME>
            <UCODE>UQA440</UCODE>
            <UCODE_REF_LAW_CD>13000</UCODE_REF_LAW_CD>
            <actRegList>
              <ACT_NM>건축</ACT_NM>
              <REG_NM>금지</REG_NM>
              <luInfoList>
                <NODE_DESC>공장</NODE_DESC>
                <LU_REF_LAW_NM1>국토의 계획 및 이용에 관한 법률</LU_REF_LAW_NM1>
                <LU_REF_LAW_NM2></LU_REF_LAW_NM2>
                <LU_REF_LAW_NM3></LU_REF_LAW_NM3>
                <DEF_REF></DEF_REF>
              </luInfoList>
            </actRegList>
          </item>
        </items>
      </body>
    </response>
    """
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTarLandUseInfo").mock(return_value=_euckr_resp(xml))
        client = LurisClient()
        result = await client.get_act_info("11215", "UQA440", "공장")
        await client.close()

    assert result is not None
    assert result["summary"]["verdict"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_act_info_data_insufficient():
    """'관련내용 없음' 플레이스홀더 → DATA_INSUFFICIENT."""
    xml = """<?xml version="1.0" encoding="EUC-KR"?>
    <response>
      <body>
        <items>
          <item>
            <UNAME>자연녹지지역</UNAME>
            <UCODE>UQA430</UCODE>
            <UCODE_REF_LAW_CD>13000</UCODE_REF_LAW_CD>
            <actRegList>
              <ACT_NM>건축</ACT_NM>
              <REG_NM>조건부</REG_NM>
              <luInfoList>
                <NODE_DESC>관련내용 없음</NODE_DESC>
                <LU_REF_LAW_NM1></LU_REF_LAW_NM1>
                <LU_REF_LAW_NM2></LU_REF_LAW_NM2>
                <LU_REF_LAW_NM3></LU_REF_LAW_NM3>
                <DEF_REF></DEF_REF>
              </luInfoList>
            </actRegList>
          </item>
        </items>
      </body>
    </response>
    """
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTarLandUseInfo").mock(return_value=_euckr_resp(xml))
        client = LurisClient()
        result = await client.get_act_info("11215", "UQA430", "기타")
        await client.close()

    assert result is not None
    assert result["summary"]["verdict"] == "DATA_INSUFFICIENT"
    assert result["summary"]["has_real_data"] is False


@pytest.mark.asyncio
async def test_get_act_info_no_item():
    """응답에 item 없음 → None (데이터 없음 정상 케이스)."""
    xml = """<?xml version="1.0" encoding="EUC-KR"?>
    <response><body><items></items></body></response>
    """
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTarLandUseInfo").mock(return_value=_euckr_resp(xml))
        client = LurisClient()
        result = await client.get_act_info("11215", "UQA430", "주택")
        await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_get_act_info_service_error_not_cached():
    """공공데이터포털 서비스 에러(throttle/quota) → None 반환, 캐싱 금지."""
    service_error_xml = """<?xml version="1.0"?>
    <OpenAPI_ServiceResponse>
      <cmmMsgHeader>
        <returnReasonCode>22</returnReasonCode>
        <errMsg>SERVICE_KEY_IS_NOT_REGISTERED</errMsg>
      </cmmMsgHeader>
    </OpenAPI_ServiceResponse>
    """
    async with respx.mock:
        respx.get(f"{LURIS_BASE}/DTarLandUseInfo").mock(
            return_value=_euckr_resp(service_error_xml)
        )
        client = LurisClient()
        result = await client.get_act_info("11215", "UQA430", "공장")
        await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_get_act_info_no_key(monkeypatch):
    """API 키 없으면 HTTP 호출 없이 None 반환."""
    monkeypatch.delenv("LURIS_API_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_API_KEY", raising=False)
    async with respx.mock:
        client = LurisClient()
        result = await client.get_act_info("11215", "UQA430", "주택")
        call_count = respx.calls.call_count
        await client.close()

    assert result is None
    assert call_count == 0
