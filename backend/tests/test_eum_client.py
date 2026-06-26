"""EumClient 오프라인 모킹 테스트 (respx).

토지이음 API 는 XML 응답(3.8 개발인허가만 JSON)을 반환하므로
픽스처는 XML 문자열로 구성한다.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from services.eum_client import EumClient

EUM_BASE = "https://api.eum.go.kr/web/Rest"


# ─── 공통 픽스처 ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _eum_env(monkeypatch):
    monkeypatch.setenv("EUM_ID", "test-id")
    monkeypatch.setenv("EUM_KEY", "test-key")


# ─── XML 응답 빌더 ────────────────────────────────────────────────────────────

def _xml_resp(body: str) -> httpx.Response:
    return httpx.Response(200, text=f'<?xml version="1.0" encoding="UTF-8"?>\n{body}')


def _error_xml() -> httpx.Response:
    return _xml_resp("<Root><ERROR_CODE>ERR-002</ERROR_CODE><ERROR_MSG>권한 없음</ERROR_MSG></Root>")


# ─── available 속성 ───────────────────────────────────────────────────────────

def test_available_no_keys(monkeypatch):
    monkeypatch.delenv("EUM_ID", raising=False)
    monkeypatch.delenv("EUM_KEY", raising=False)
    client = EumClient()
    assert client.available is False


def test_available_partial_key(monkeypatch):
    monkeypatch.delenv("EUM_KEY", raising=False)
    client = EumClient()
    assert client.available is False


def test_available_with_keys():
    client = EumClient()
    assert client.available is True


# ─── search_area_codes ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_area_codes_success():
    xml = """
    <Areas>
      <AreaCd><AREA_CD>11000</AREA_CD><AREA_NM>서울특별시</AREA_NM></AreaCd>
      <AreaCd><AREA_CD>26000</AREA_CD><AREA_NM>부산광역시</AREA_NM></AreaCd>
    </Areas>
    """
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/searchArea").mock(return_value=_xml_resp(xml))
        client = EumClient()
        result = await client.search_area_codes()
        await client.close()

    assert len(result) == 2
    assert result[0]["area_cd"] == "11000"
    assert result[0]["area_nm"] == "서울특별시"


@pytest.mark.asyncio
async def test_search_area_codes_unavailable(monkeypatch):
    monkeypatch.delenv("EUM_ID", raising=False)
    monkeypatch.delenv("EUM_KEY", raising=False)
    async with respx.mock:
        client = EumClient()
        result = await client.search_area_codes()
        call_count = respx.calls.call_count
        await client.close()

    assert result == []
    assert call_count == 0


# ─── search_zone_codes ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_zone_codes_success():
    xml = """
    <Zones>
      <ZoneCd>
        <UCODE>UQA430</UCODE>
        <UNAME>자연녹지지역</UNAME>
        <LAW_CD>1300</LAW_CD>
        <LAW_NM>국토의 계획 및 이용에 관한 법률</LAW_NM>
      </ZoneCd>
    </Zones>
    """
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/searchZone").mock(return_value=_xml_resp(xml))
        client = EumClient()
        result = await client.search_zone_codes("11215", uname="자연녹지지역")
        await client.close()

    assert len(result) == 1
    assert result[0]["ucode"] == "UQA430"
    assert result[0]["uname"] == "자연녹지지역"
    assert result[0]["law_nm"] == "국토의 계획 및 이용에 관한 법률"


@pytest.mark.asyncio
async def test_search_zone_codes_empty():
    xml = "<Zones></Zones>"
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/searchZone").mock(return_value=_xml_resp(xml))
        client = EumClient()
        result = await client.search_zone_codes("99999")
        await client.close()

    assert result == []


# ─── get_act_restriction ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_act_restriction_success():
    xml = """
    <ActRegs>
      <ActReg>
        <UCODE>UQA430</UCODE>
        <UNAME>자연녹지지역</UNAME>
        <UCODE_REF_LAW_CD>13000</UCODE_REF_LAW_CD>
        <UCODE_REF_LAW_NM>국토의 계획 및 이용에 관한 법률</UCODE_REF_LAW_NM>
        <actRegList>
          <ACT_NM>건축</ACT_NM>
          <REG_NM>허용가능</REG_NM>
          <QNODE_CONDS>
            <item>제한조건1</item>
          </QNODE_CONDS>
          <luInfoList>
            <NODE_DESC>단독주택</NODE_DESC>
            <LU_REF_LAW_NM1>국토의 계획 및 이용에 관한 법률</LU_REF_LAW_NM1>
            <LU_REF_LAW_NM2></LU_REF_LAW_NM2>
            <LU_REF_LAW_NM3></LU_REF_LAW_NM3>
            <DEF_REF></DEF_REF>
          </luInfoList>
        </actRegList>
        <QnodeCond>
          <QNODE_DESC>건축제한 조건</QNODE_DESC>
          <RNUM>1</RNUM>
        </QnodeCond>
      </ActReg>
    </ActRegs>
    """
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/arLandUseInfo").mock(return_value=_xml_resp(xml))
        client = EumClient()
        result = await client.get_act_restriction("11215", ["UQA430"], land_use_nm="단독주택")
        await client.close()

    assert len(result) == 1
    item = result[0]
    assert item["ucode"] == "UQA430"
    assert item["uname"] == "자연녹지지역"
    assert len(item["act_reg_list"]) == 1
    act = item["act_reg_list"][0]
    assert act["act_nm"] == "건축"
    assert act["reg_nm"] == "허용가능"
    assert act["lu_info_list"][0]["node_desc"] == "단독주택"
    assert item["qnode_conds"][0]["qnode_desc"] == "건축제한 조건"


@pytest.mark.asyncio
async def test_get_act_restriction_empty_ucodes():
    """빈 ucode_list → HTTP 호출 없이 [] 반환."""
    async with respx.mock:
        client = EumClient()
        result = await client.get_act_restriction("11215", [])
        call_count = respx.calls.call_count
        await client.close()

    assert result == []
    assert call_count == 0


# ─── get_notices ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_notices_success():
    xml = """
    <Root>
      <totalSize>1</totalSize>
      <totalPage>1</totalPage>
      <listSize>1</listSize>
      <pageNo>1</pageNo>
      <ArMap>
        <TITLE>도시관리계획 변경결정 고시</TITLE>
        <AUTHOR>서울특별시</AUTHOR>
        <NTC_DATE>20260601</NTC_DATE>
        <LINK>https://example.com/notice/123</LINK>
        <SUMMARY>영등포구 도시관리계획 변경</SUMMARY>
      </ArMap>
    </Root>
    """
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/arMapList").mock(return_value=_xml_resp(xml))
        client = EumClient()
        result = await client.get_notices("11215", "20260101", "20260630")
        await client.close()

    assert result["total_size"] == 1
    assert result["total_page"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["title"] == "도시관리계획 변경결정 고시"
    assert item["author"] == "서울특별시"
    assert item["ntc_date"] == "20260601"


# ─── get_dev_permits ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_dev_permits_success():
    json_body = {
        "siteCode": "11215",
        "pageNo": 1,
        "totalPage": 2,
        "cnt": 35,
        "list": [
            {"prmisnNm": "건축허가", "bldNm": "영등포타워", "prmisnDe": "20260520"},
        ],
    }
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/sDevList").mock(
            return_value=httpx.Response(200, json=json_body)
        )
        client = EumClient()
        result = await client.get_dev_permits("11215", "20260520")
        await client.close()

    assert result["site_code"] == "11215"
    assert result["total_page"] == 2
    assert result["cnt"] == 35
    assert len(result["list"]) == 1


@pytest.mark.asyncio
async def test_get_dev_permits_unavailable(monkeypatch):
    """키 없으면 빈 dict 반환."""
    monkeypatch.delenv("EUM_ID", raising=False)
    monkeypatch.delenv("EUM_KEY", raising=False)
    async with respx.mock:
        client = EumClient()
        result = await client.get_dev_permits("11215", "20260520")
        await client.close()

    assert result["cnt"] == 0
    assert result["list"] == []


# ─── 에러 응답 처리 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_code_returns_empty():
    """ERROR_CODE 응답 → [] 반환 (graceful degrade)."""
    async with respx.mock:
        respx.get(f"{EUM_BASE}/OP/searchArea").mock(return_value=_error_xml())
        client = EumClient()
        result = await client.search_area_codes()
        await client.close()

    assert result == []
