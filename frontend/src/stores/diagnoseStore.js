import { create } from 'zustand'

const emptyFormData = {
  address: '',
  building_use: '',
  site_area: '',
  building_area: '',
  total_floor_area: '',
  floors_above: '',
  floors_below: '0',
  height: '',
  units: '',
  road_width: '',
  landscape_area: '',
  pnu: '',
}

export const useDiagnoseStore = create((set) => ({
  // 입력
  formData: { ...emptyFormData },

  // 선택된 주소
  selectedAddress: null,

  // 기본 진단 결과
  result: null,
  loading: false,
  error: null,

  // Phase 3 상태
  whatIfResult: null,
  whatIfLoading: false,
  whatIfOverrides: null,   // 사용자가 조정한 슬라이더 값들

  setFormData: (patch) =>
    set((s) => ({ formData: { ...s.formData, ...patch } })),

  setSelectedAddress: (addr) =>
    set({
      selectedAddress: addr,
      formData: {
        ...emptyFormData,
        address: addr?.road_addr || addr?.jibun_addr || '',
        pnu: addr?.pnu || '',
      },
      result: null,
      whatIfResult: null,
      whatIfOverrides: null,
      error: null,
    }),

  setResult: (result) =>
    set({
      result,
      loading: false,
      error: null,
      // 기본 진단이 다시 돌면 What-if 초기화
      whatIfResult: null,
      whatIfOverrides: null,
    }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
  reset: () =>
    set({
      result: null,
      error: null,
      whatIfResult: null,
      whatIfOverrides: null,
    }),

  // What-if
  setWhatIfLoading: (whatIfLoading) => set({ whatIfLoading }),
  setWhatIfResult: (whatIfResult) => set({ whatIfResult, whatIfLoading: false }),
  setWhatIfOverrides: (whatIfOverrides) => set({ whatIfOverrides }),
  resetWhatIf: () => set({ whatIfResult: null, whatIfOverrides: null }),
}))
