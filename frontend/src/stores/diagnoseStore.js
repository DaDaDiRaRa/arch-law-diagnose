import { create } from 'zustand'
import { api } from '../utils/api'

const emptyFormData = {
  address: '',
  building_use: '',
  building_use_detail: '',        // 세부/복합 용도 (자유 입력)
  zone_district: '',              // 지역지구 (자유 입력, 미입력 시 VWorld 자동)
  site_area: '',
  building_area: '',
  floor_area_above: '',          // 지상 연면적 (필수, 주차장 포함 전체)
  floor_area_below: '',          // 지하 연면적 (선택, 용적률 산정 제외)
  floor_area_parking_above: '',  // 지상 주차장 면적 (선택, 부속용도 — 용적률 산정 제외)
  floor_area_refuge: '',         // 피난안전구역 면적 (선택, 초고층 한정 — 용적률 산정 제외)
  floor_area_attic_refuge: '',   // 경사지붕 대피공간 면적 (선택, 11층 이상 — 용적률 산정 제외)
  floors_above: '',
  floors_below: '0',
  height: '',
  units: '',
  road_width: '',
  landscape_area: '',
  provided_parking_spaces: '',   // 계획 주차대수
  public_open_space_area: '',    // 공개공지 면적

  // 용적률 완화 — 모두 선택
  green_grade: '',                 // 녹색건축 인증 등급
  energy_grade: '',                // 에너지효율 등급
  smart_grade: '',                 // 지능형건축물 인증 등급
  long_life_grade: '',             // 장수명주택 인증 등급 (공동주택 한정)
  far_limit_manual_override: '',   // 용적률 한도 직접 지정 (심의/지구단위/정비사업 등)
  relief_reason_manual: '',        // 한도 변경 사유

  urban_facility_exclude_area: '', // 도시계획시설 저촉 면적 (선택, 자동 추정 override)

  // 높이·일조 보강 입력 (선택)
  north_setback_m: '',              // 정북 인접대지경계선까지 실제 이격거리 (m)
  adjacent_zone_north: '',          // 정북 인접대지 용도지역
  road_20m_adjacent: '',            // 너비 20m+ 도로 접함 (yes/no/'')
  street_block_max_height_m: '',    // 가로구역별 최고높이 지정값 (m)

  pnu: '',
}

const emptyParcel = () => ({
  address: '',
  pnu: '',
  site_area: '',
  zone_use_override: '',
  selectedAddress: null,
})

export const useDiagnoseStore = create((set) => ({
  // 입력
  formData: { ...emptyFormData },

  // 선택된 주소
  selectedAddress: null,

  // 주소 선택 시 자동 조회된 토지 정보 (VWorld)
  autoLandInfo: null,           // { zone_use, zone_district, zone_area, land_category, ... } | null
  autoLandLoading: false,

  // 합필 모드 — 추가 필지 (기본 형식은 formData/selectedAddress 가 1번 필지 역할)
  additionalParcels: [],

  // 기본 진단 결과
  result: null,
  loading: false,
  error: null,

  setFormData: (patch) =>
    set((s) => ({ formData: { ...s.formData, ...patch } })),

  setSelectedAddress: (addr) => {
    set({
      selectedAddress: addr,
      formData: {
        ...emptyFormData,
        address: addr?.road_addr || addr?.jibun_addr || '',
        pnu: addr?.pnu || '',
      },
      additionalParcels: [],
      result: null,
      error: null,
      autoLandInfo: null,
      autoLandLoading: false,
    })
    // 자동 토지 정보 조회 (PNU 또는 주소 기반)
    const pnu = addr?.pnu || ''
    const address = addr?.road_addr || addr?.jibun_addr || ''
    if (!pnu && !address) return
    set({ autoLandLoading: true })
    api
      .fetchLandInfo({ pnu, address })
      .then((info) => {
        set((s) => ({
          autoLandInfo: info,
          autoLandLoading: false,
          // 사용자가 아직 직접 수정 안 한 경우에만 자동 채움
          formData: {
            ...s.formData,
            zone_use_override: s.formData.zone_use_override || info.zone_use || '',
            zone_district: s.formData.zone_district || info.zone_district || '',
            road_width: s.formData.road_width || (info.road_width_auto != null ? String(info.road_width_auto) : ''),
          },
        }))
      })
      .catch(() => set({ autoLandLoading: false }))
  },

  addParcel: () =>
    set((s) => ({ additionalParcels: [...s.additionalParcels, emptyParcel()] })),

  removeParcel: (idx) =>
    set((s) => ({
      additionalParcels: s.additionalParcels.filter((_, i) => i !== idx),
    })),

  updateParcel: (idx, patch) =>
    set((s) => ({
      additionalParcels: s.additionalParcels.map((p, i) =>
        i === idx ? { ...p, ...patch } : p,
      ),
    })),

  setParcelAddress: (idx, addr) =>
    set((s) => ({
      additionalParcels: s.additionalParcels.map((p, i) =>
        i === idx
          ? {
              ...p,
              selectedAddress: addr,
              address: addr?.road_addr || addr?.jibun_addr || '',
              pnu: addr?.pnu || '',
            }
          : p,
      ),
    })),

  setResult: (result) =>
    set({
      result,
      loading: false,
      error: null,
    }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
  reset: () =>
    set({
      result: null,
      error: null,
    }),
}))
