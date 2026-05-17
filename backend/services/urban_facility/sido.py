"""시·도 코드 ↔ SHP 폴더 매핑."""
from pathlib import Path

# 시·도 5자리 코드 (행정표준)
SIDO_CODES: dict[str, str] = {
    "11000": "서울특별시",
    "26000": "부산광역시",
    "27000": "대구광역시",
    "28000": "인천광역시",
    "29000": "광주광역시",
    "30000": "대전광역시",
    "31000": "울산광역시",
    "36000": "세종특별자치시",
    "41000": "경기도",
    "43000": "충청북도",
    "44000": "충청남도",
    "46000": "전라남도",
    "47000": "경상북도",
    "48000": "경상남도",
    "50000": "제주특별자치도",
    "51000": "강원특별자치도",
    "52000": "전북특별자치도",
}


def pnu_to_sido(pnu: str) -> str | None:
    """PNU 19자리 → 시·도 5자리 코드."""
    if not pnu or len(pnu) < 5:
        return None
    return pnu[:2] + "000"


def resolve_sido_folder(shp_root: Path, sido_code: str) -> Path | None:
    """시·도 코드로 SHP 폴더 경로 결정. UPIS 우선, 없으면 KLIP.

    shp_root 자체가 존재하지 않으면 None 반환
    — graceful degrade (SHP 미배포 환경에서도 다른 진단은 진행).
    """
    if not shp_root.exists() or not shp_root.is_dir():
        return None
    # 예: 11000 → UPIS_003_*_11000 또는 KLIP_003_*_11000
    for prefix in ("UPIS_003_", "KLIP_003_"):
        for d in shp_root.iterdir():
            if d.is_dir() and d.name.startswith(prefix) and d.name.endswith(f"_{sido_code}"):
                return d
    return None
