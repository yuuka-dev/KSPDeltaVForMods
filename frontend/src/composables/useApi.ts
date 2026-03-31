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

const API_ORIGIN = import.meta.env.DEV
  ? `${window.location.protocol}//${window.location.host}`
  : 'http://localhost:8000'
const API_PREFIX = import.meta.env.DEV ? '/api' : ''

function buildUrl(path: string, lang?: string): string {
  const url = new URL(`${API_PREFIX}${path}`, API_ORIGIN)
  if (lang) {
    url.searchParams.set('lang', lang)
  }
  return url.toString()
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  lang?: string,
): Promise<T> {
  const response = await fetch(buildUrl(path, lang), {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

/** Wait for the backend to become available (used by Tauri on startup). */
export async function waitForBackend(
  maxRetries = 60,
  intervalMs = 1000,
): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(buildUrl('/health'))
      if (res.ok) return true
    } catch {
      // Backend not ready yet
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  return false
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
      const response = await fetch(buildUrl('/upload-config', lang), {
        method: 'POST',
        body: formData,
      })
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
