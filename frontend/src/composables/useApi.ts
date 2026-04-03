import { invoke } from '@tauri-apps/api/core'
import { useToast } from 'primevue/usetoast'
import type {
  AtmoProfileResponse,
  BodyDetail,
  BodySummary,
  DestinationEntry,
  HealthResponse,
  HohmannResponse,
  LaunchResponse,
  RouteResponse,
  ScanRequest,
  SystemResponse,
  TsiolkovskyResponse,
  UploadResponse,
} from '@/types/api'

export function useApi(lang?: string) {
  const toast = useToast()

  function handleError(err: unknown): void {
    const message = err instanceof Error ? err.message : String(err)
    toast.add({ severity: 'error', summary: 'Error', detail: message, life: 5000 })
  }

  return {
    health: () => invoke<HealthResponse>('health'),
    listBodies: () => invoke<BodySummary[]>('list_bodies', { lang }),
    getBody: (name: string) => invoke<BodyDetail>('get_body', { name, lang }),
    getBodyMoons: (name: string) =>
      invoke<DestinationEntry[]>('get_body_moons', { name }),

    uploadConfig: (fileContent: string) =>
      invoke<UploadResponse>('upload_config', { fileContent }),

    scan: (req: ScanRequest) =>
      invoke<UploadResponse>('scan_gamedata', {
        path: req.gamedata_path,
        exclude: req.exclude_dirs,
      }),

    calcLaunch: (req: { body_name: string; target_altitude: number }) =>
      invoke<LaunchResponse>('calc_launch', {
        bodyName: req.body_name,
        targetAltitude: req.target_altitude,
      }),

    calcHohmann: (req: { body_name: string; parking_altitude: number; target_sma: number }) =>
      invoke<HohmannResponse>('calc_hohmann', {
        bodyName: req.body_name,
        parkingAlt: req.parking_altitude,
        targetSma: req.target_sma,
      }),

    calcTsiolkovsky: (req: { delta_v: number; isp: number; wet_mass: number }) =>
      invoke<TsiolkovskyResponse>('calc_tsiolkovsky', {
        deltaV: req.delta_v,
        isp: req.isp,
        wetMass: req.wet_mass,
      }),

    getSystem: () => invoke<SystemResponse>('get_system'),
    getDestinations: () => invoke<DestinationEntry[]>('get_destinations'),

    calcRoute: (req: { destination: string | null; moon: string | null }) =>
      invoke<RouteResponse>('calc_route', {
        destination: req.destination,
        moon: req.moon,
      }),

    getAtmoProfile: (name: string, steps?: number) =>
      invoke<AtmoProfileResponse>('get_atmo_profile', { name, steps }),

    handleError,
  }
}
