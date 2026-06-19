import { create } from 'zustand'
import { api } from '../utils/api'

const emptyFormData = {
  // 대지 정보
  address: '',
  pnu: '',
  zone_use_override: '',
  zone_district: '',
  road_width: '',
  site_area_override: '',

  // 시설 유형
  facility_use: '',
  building_use_detail: '',
  applicant_type: '개인',

  // 공모 요구치 — 모두 선택
  target_floor_area_sqm: '',
  target_building_coverage_pct: '',
  target_far_pct: '',
  target_max_height_m: '',
  target_floors_above: '',
  target_parking_count: '',
  target_open_space_sqm: '',
  target_units: '',
  unit_exclusive_area: '',
}

export const useFeasibilityStore = create((set) => ({
  formData: { ...emptyFormData },
  selectedAddress: null,
  autoLandInfo: null,
  autoLandLoading: false,

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
      result: null,
      error: null,
      autoLandInfo: null,
      autoLandLoading: false,
    })
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
          formData: {
            ...s.formData,
            zone_use_override: s.formData.zone_use_override || info.zone_use || '',
            zone_district: s.formData.zone_district || info.zone_district || '',
            road_width:
              s.formData.road_width ||
              (info.road_width_auto != null ? String(info.road_width_auto) : ''),
          },
        }))
      })
      .catch(() => set({ autoLandLoading: false }))
  },

  runFeasibility: async () => {
    const { formData } = useFeasibilityStore.getState()
    if (!formData.address) {
      set({ error: '주소를 입력해주세요' })
      return
    }
    if (!formData.facility_use) {
      set({ error: '시설 용도를 선택해주세요' })
      return
    }
    set({ loading: true, error: null })

    const toNum = (v) => {
      if (v === '' || v == null) return null
      const n = parseFloat(v)
      return Number.isFinite(n) ? n : null
    }
    const toInt = (v) => {
      if (v === '' || v == null) return null
      const n = parseInt(v, 10)
      return Number.isFinite(n) ? n : null
    }

    const payload = {
      address: formData.address,
      pnu: formData.pnu || null,
      facility_use: formData.facility_use,
      building_use_detail: formData.building_use_detail || null,
      applicant_type: formData.applicant_type || '개인',
      zone_use_override: formData.zone_use_override || null,
      zone_district: formData.zone_district || null,
      road_width: toNum(formData.road_width),
      site_area_override: toNum(formData.site_area_override),
      target_floor_area_sqm: toNum(formData.target_floor_area_sqm),
      target_building_coverage_pct: toNum(formData.target_building_coverage_pct),
      target_far_pct: toNum(formData.target_far_pct),
      target_max_height_m: toNum(formData.target_max_height_m),
      target_floors_above: toInt(formData.target_floors_above),
      target_parking_count: toInt(formData.target_parking_count),
      target_open_space_sqm: toNum(formData.target_open_space_sqm),
      target_units: toInt(formData.target_units),
      unit_exclusive_area: toNum(formData.unit_exclusive_area),
    }

    try {
      const result = await api.feasibility(payload)
      set({ result, loading: false })
    } catch (e) {
      set({ error: e.message || '사업성 검토 실패', loading: false })
    }
  },

  reset: () =>
    set({
      formData: { ...emptyFormData },
      selectedAddress: null,
      autoLandInfo: null,
      result: null,
      error: null,
    }),
}))
