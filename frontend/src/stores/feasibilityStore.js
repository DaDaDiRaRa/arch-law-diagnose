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

// 대안 비교(What-If)에서 조정 가능한 완화 레버
const emptyLevers = {
  facility_use: '',
  green_grade: '',
  energy_grade: '',
  pilot_project: false,
  building_agreement: false,
  rema_zone: false,
  easy_remodel: false,
  target_open_space_sqm: '',
}

// formData(+레버 오버라이드)로 /api/feasibility/run 페이로드 생성
function buildFeasibilityPayload(formData, levers = null) {
  const f = formData
  const L = levers || {}
  const pick = (key) => (levers && L[key] !== undefined ? L[key] : f[key])
  return {
    address: f.address,
    pnu: f.pnu || null,
    facility_use: pick('facility_use'),
    building_use_detail: f.building_use_detail || null,
    applicant_type: f.applicant_type || '개인',
    zone_use_override: f.zone_use_override || null,
    zone_district: f.zone_district || null,
    road_width: toNum(f.road_width),
    site_area_override: toNum(f.site_area_override),
    target_floor_area_sqm: toNum(f.target_floor_area_sqm),
    target_building_coverage_pct: toNum(f.target_building_coverage_pct),
    target_far_pct: toNum(f.target_far_pct),
    target_max_height_m: toNum(f.target_max_height_m),
    target_floors_above: toInt(f.target_floors_above),
    target_parking_count: toInt(f.target_parking_count),
    target_open_space_sqm: toNum(pick('target_open_space_sqm')),
    target_units: toInt(f.target_units),
    unit_exclusive_area: toNum(f.unit_exclusive_area),
    site_label: f.site_label || null,
    // 완화 레버
    green_grade: L.green_grade || null,
    energy_grade: L.energy_grade || null,
    pilot_project: !!L.pilot_project,
    building_agreement: !!L.building_agreement,
    rema_zone: !!L.rema_zone,
    easy_remodel: !!L.easy_remodel,
  }
}

let _altSeq = 0
let _siteSeq = 0

// 다중 비교용 부지 엔트리 (formData와 같은 필드명 → buildFeasibilityPayload 재사용)
function makeSite(seed = {}) {
  _siteSeq += 1
  const s = (v) => (v == null ? '' : String(v))
  return {
    id: _siteSeq,
    site_label: seed.site_label || `부지 ${_siteSeq}`,
    address: seed.address || '',
    pnu: seed.pnu || '',
    zone_use_override: seed.zone_use_override || '',
    site_area_override: s(seed.site_area_override),
    facility_use: seed.facility_use || '',
    applicant_type: seed.applicant_type || '개인',
    target_floor_area_sqm: s(seed.target_floor_area_sqm),
    target_building_coverage_pct: s(seed.target_building_coverage_pct),
    target_far_pct: s(seed.target_far_pct),
    target_max_height_m: s(seed.target_max_height_m),
    target_open_space_sqm: s(seed.target_open_space_sqm),
    building_use_detail: seed.building_use_detail || '',
  }
}

export const useFeasibilityStore = create((set, get) => ({
  formData: { ...emptyFormData },
  selectedAddress: null,
  autoLandInfo: null,
  autoLandLoading: false,

  result: null,
  loading: false,
  error: null,

  // 공모지침 불러오기 적용 상태
  briefApplied: null,

  // 다중 대지 비교
  multiSites: [],
  multiResults: null,
  multiLoading: false,
  multiError: null,

  // 자동 제안 대안 중 선택된 키 (강조 표시용)
  selectedAltKey: null,

  // 대안 비교(What-If)
  whatifOpen: false,
  whatifLevers: { ...emptyLevers },
  whatifResult: null,
  whatifLoading: false,
  whatifError: null,
  alternatives: [],

  setFormData: (patch) =>
    set((s) => ({ formData: { ...s.formData, ...patch } })),

  // 공모지침에서 불러온 부지 → 폼의 공모 요구치 채우기
  // 주소·신청주체·인증(완화 레버)까지 자동 채움. 용도는 매핑표 부재로 힌트만.
  applyBriefSite: (site, meta = {}) => {
    const numOrEmpty = (v) => (v == null ? '' : String(v))
    const relief = meta.relief || {}
    set((s) => ({
      formData: {
        ...s.formData,
        site_area_override: numOrEmpty(site.site_area_sqm),
        target_floor_area_sqm: numOrEmpty(site.target_floor_area_sqm),
        target_building_coverage_pct: numOrEmpty(site.target_building_coverage_pct),
        target_far_pct: numOrEmpty(site.target_far_pct),
        target_max_height_m: numOrEmpty(site.target_max_height_m),
        target_open_space_sqm: numOrEmpty(site.target_open_space_sqm),
        // 주소가 brief에 있으면만 채움
        address: site.address || s.formData.address,
        zone_use_override: site.zoning || s.formData.zone_use_override,
        // 발주처가 공공기관이면 신청주체 자동 설정
        applicant_type: meta.applicant_type || s.formData.applicant_type,
        // 용도 힌트는 세부 용도란에 참고용으로
        building_use_detail:
          s.formData.building_use_detail ||
          (site.facility_hint ? `[공모] ${site.facility_hint}` : ''),
      },
      briefApplied: {
        competition_name: meta.competition_name || '',
        site_id: site.site_id || '',
        facility_hint: site.facility_hint || '',
        open_space_notes: site.open_space_notes || '',
        applicant_type: meta.applicant_type || '',
        // 대안 비교(What-If)에서 완화 레버 시드로 사용
        relief: {
          green_grade: relief.green_grade || '',
          energy_grade: relief.energy_grade || '',
          renewable_pct: relief.renewable_pct ?? null,
          bf_grade: relief.bf_grade || '',
          certifications: relief.certifications || [],
        },
      },
    }))
  },

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
    const { formData } = get()
    if (!formData.address) {
      set({ error: '주소를 입력해주세요' })
      return
    }
    if (!formData.facility_use) {
      set({ error: '시설 용도를 선택해주세요' })
      return
    }
    set({ loading: true, error: null })

    try {
      const result = await api.feasibility(buildFeasibilityPayload(formData))
      set({ result, loading: false })
    } catch (e) {
      set({ error: e.message || '사업성 검토 실패', loading: false })
    }
  },

  // ── 대안 비교(What-If) ──────────────────────────────────────────────
  openWhatif: () => {
    const { formData, whatifOpen, briefApplied } = get()
    if (whatifOpen) {
      set({ whatifOpen: false })
      return
    }
    // 레버를 현재 입력값으로 시드. 공모지침이 요구한 인증이 있으면 미리 켜둠.
    const r = briefApplied?.relief || {}
    set({
      whatifOpen: true,
      whatifLevers: {
        ...emptyLevers,
        facility_use: formData.facility_use || '',
        target_open_space_sqm: formData.target_open_space_sqm || '',
        green_grade: r.green_grade || '',
        energy_grade: r.energy_grade || '',
      },
    })
    get().runWhatif()
  },

  // 자동 제안 대안 1개 선택 → 그 완화 조합을 What-If에 시드하고 열기(미세조정 가능)
  applyAlternative: (alt) => {
    const { formData } = get()
    const lv = alt?.levers || {}
    set({
      whatifOpen: true,
      whatifLevers: {
        ...emptyLevers,
        facility_use: formData.facility_use || '',
        target_open_space_sqm: formData.target_open_space_sqm || '',
        green_grade: lv.green_grade || '',
        energy_grade: lv.energy_grade || '',
        pilot_project: !!lv.pilot_project,
        building_agreement: !!lv.building_agreement,
        rema_zone: !!lv.rema_zone,
        easy_remodel: !!lv.easy_remodel,
      },
      selectedAltKey: alt?.key || null,
    })
    get().runWhatif()
  },

  setLever: (patch) => {
    set((s) => ({ whatifLevers: { ...s.whatifLevers, ...patch }, selectedAltKey: null }))
    get().runWhatif()
  },

  runWhatif: async () => {
    const { formData, whatifLevers } = get()
    if (!formData.address || !whatifLevers.facility_use) return
    set({ whatifLoading: true, whatifError: null })
    try {
      const result = await api.feasibility(
        buildFeasibilityPayload(formData, whatifLevers)
      )
      set({ whatifResult: result, whatifLoading: false })
    } catch (e) {
      set({ whatifError: e.message || '대안 계산 실패', whatifLoading: false })
    }
  },

  saveAlternative: (label) => {
    const { whatifResult, whatifLevers, alternatives } = get()
    if (!whatifResult) return
    _altSeq += 1
    const alt = {
      id: _altSeq,
      label: label || `대안 ${alternatives.length + 1}`,
      levers: { ...whatifLevers },
      proposal: whatifResult.proposal,
      recommendation: whatifResult.overall_recommendation,
      review_count: whatifResult.review_burden?.count_required ?? null,
    }
    set({ alternatives: [...alternatives, alt] })
  },

  removeAlternative: (id) =>
    set((s) => ({ alternatives: s.alternatives.filter((a) => a.id !== id) })),

  renameAlternative: (id, label) =>
    set((s) => ({
      alternatives: s.alternatives.map((a) =>
        a.id === id ? { ...a, label } : a
      ),
    })),

  clearAlternatives: () => set({ alternatives: [] }),

  // ── 다중 대지 비교 ──────────────────────────────────────────────────
  addMultiSite: (seed) =>
    set((s) => ({ multiSites: [...s.multiSites, makeSite(seed)] })),

  updateMultiSite: (id, patch) =>
    set((s) => ({
      multiSites: s.multiSites.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),

  removeMultiSite: (id) =>
    set((s) => ({ multiSites: s.multiSites.filter((m) => m.id !== id) })),

  clearMultiSites: () => set({ multiSites: [], multiResults: null, multiError: null }),

  // 공모지침의 모든 부지를 비교 엔트리로 적재
  loadBriefSitesToMulti: (mapped) => {
    const sites = (mapped?.sites || []).map((s) =>
      makeSite({
        site_label: s.site_id || mapped.competition_name,
        address: s.address,
        zone_use_override: s.zoning,
        applicant_type: mapped.applicant_type || '개인',
        site_area_override: s.site_area_sqm,
        target_floor_area_sqm: s.target_floor_area_sqm,
        target_building_coverage_pct: s.target_building_coverage_pct,
        target_far_pct: s.target_far_pct,
        target_max_height_m: s.target_max_height_m,
        target_open_space_sqm: s.target_open_space_sqm,
        building_use_detail: s.facility_hint ? `[공모] ${s.facility_hint}` : '',
      })
    )
    set({ multiSites: sites, multiResults: null, multiError: null })
  },

  runMulti: async () => {
    const { multiSites } = get()
    if (multiSites.length === 0) {
      set({ multiError: '비교할 부지를 추가하세요' })
      return
    }
    const missing = multiSites.filter((m) => !m.address || !m.facility_use)
    if (missing.length > 0) {
      set({
        multiError: `주소·용도가 비어있는 부지가 ${missing.length}개 있습니다. 모두 입력해주세요.`,
      })
      return
    }
    set({ multiLoading: true, multiError: null })
    try {
      const payloads = multiSites.map((m) => buildFeasibilityPayload(m))
      const res = await api.feasibilityMulti(payloads)
      set({ multiResults: res.results || [], multiLoading: false })
    } catch (e) {
      set({ multiError: e.message || '다중 비교 실패', multiLoading: false })
    }
  },

  reset: () =>
    set({
      formData: { ...emptyFormData },
      selectedAddress: null,
      autoLandInfo: null,
      result: null,
      error: null,
      briefApplied: null,
      selectedAltKey: null,
      multiSites: [],
      multiResults: null,
      multiError: null,
      whatifOpen: false,
      whatifLevers: { ...emptyLevers },
      whatifResult: null,
      whatifError: null,
      alternatives: [],
    }),
}))
