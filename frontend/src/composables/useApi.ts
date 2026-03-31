import { useToast } from 'primevue/usetoast'
import type {
  AtmoProfileResponse,
  BodyDetail,
  BodySummary,
  HealthResponse,
  HohmannRequest,
  HohmannResponse,
  LaunchRequest,
  LaunchResponse,
  RouteRequest,
  RouteResponse,
  ScanRequest,
  SystemResponse,
  TsiolkovskyRequest,
  TsiolkovskyResponse,
  UploadResponse,
  DestinationEntry,
} from '@/types/api'

const BASE_URL = import.meta.env.DEV ? '/api' : 'http://localhost:8000'

async function request<T>(
  path: string,
  options: RequestInit = {},
  lang?: string,
): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)
  if (lang) {
    url.searchParams.set('lang', lang)
  }
  const response = await fetch(url.toString(), {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function useApi(lang?: string) {
  const toast = useToast()

  function handleError(err: unknown): void {
    const message = err instanceof Error ? err.message : String(err)
    toast.add({ severity: 'error', summary: 'API Error', detail: message, life: 5000 })
  }

  return {
    health: () => request<HealthResponse>('/health'),
    listBodies: () => request<BodySummary[]>('/bodies', {}, lang),
    getBody: (name: string) => request<BodyDetail>(`/bodies/${encodeURIComponent(name)}`, {}, lang),
    getBodyMoons: (name: string) =>
      request<DestinationEntry[]>(`/bodies/${encodeURIComponent(name)}/moons`),

    uploadConfig: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const url = `${BASE_URL}/upload-config${lang ? `?lang=${lang}` : ''}`
      const response = await fetch(url, { method: 'POST', body: formData })
      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(body.detail ?? `HTTP ${response.status}`)
      }
      return response.json() as Promise<UploadResponse>
    },

    scan: (req: ScanRequest) =>
      request<UploadResponse>('/scan', { method: 'POST', body: JSON.stringify(req) }),

    calcLaunch: (req: LaunchRequest) =>
      request<LaunchResponse>('/calc/launch', { method: 'POST', body: JSON.stringify(req) }, lang),
    calcHohmann: (req: HohmannRequest) =>
      request<HohmannResponse>('/calc/hohmann', { method: 'POST', body: JSON.stringify(req) }, lang),
    calcTsiolkovsky: (req: TsiolkovskyRequest) =>
      request<TsiolkovskyResponse>('/calc/tsiolkovsky', { method: 'POST', body: JSON.stringify(req) }, lang),

    getSystem: () => request<SystemResponse>('/system'),
    getDestinations: () => request<DestinationEntry[]>('/system/destinations'),
    calcRoute: (req: RouteRequest) =>
      request<RouteResponse>('/calc/route', { method: 'POST', body: JSON.stringify(req) }),

    getAtmoProfile: (name: string, steps?: number) => {
      const params = steps ? `?steps=${steps}` : ''
      return request<AtmoProfileResponse>(`/atmo-profile/${encodeURIComponent(name)}${params}`, {}, lang)
    },

    handleError,
  }
}
