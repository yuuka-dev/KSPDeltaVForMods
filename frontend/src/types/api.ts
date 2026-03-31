// --- Body types ---

export interface BodySummary {
  name: string
  display_name: string
  radius: number
  gee_asl: number
  has_atmosphere: boolean
  has_ocean: boolean
}

export interface OrbitResponse {
  semi_major_axis: number
  eccentricity: number
  inclination: number
  argument_of_periapsis: number
  longitude_of_ascending_node: number
  mean_anomaly_at_epoch: number
  epoch: number
}

export interface AtmosphereResponse {
  atmosphere_depth: number
  pressure_at_sea_level: number
  temperature_at_sea_level: number
  molar_mass: number
  adiabatic_index: number
  sea_level_density: number | null
}

export interface BodyDetail {
  name: string
  display_name: string
  radius: number
  gee_asl: number
  mu: number
  has_ocean: boolean
  rotational_period: number
  soi: number
  atmosphere: AtmosphereResponse | null
  orbit: OrbitResponse | null
}

// --- Calculation types ---

export interface LaunchRequest {
  body_name: string
  target_altitude: number
}

export interface LaunchResponse {
  orbital_velocity: number
  gravity_loss: number
  drag_loss: number
  total_ideal: number
  total_rocket: number
  jet_savings: number
  total_with_jets: number
}

export interface HohmannRequest {
  body_name: string
  parking_altitude: number
  target_sma: number
}

export interface HohmannResponse {
  departure_dv: number
  arrival_dv: number
  total_dv: number
  transfer_time: number
  inward: boolean
}

export interface TsiolkovskyRequest {
  delta_v: number
  isp: number
  wet_mass: number
}

export interface TsiolkovskyResponse {
  mass_ratio: number
  fuel_fraction: number
  dry_mass: number
  fuel_mass: number
}

// --- System types ---

export interface BodyTreeNode {
  name: string
  display_name: string
  children: BodyTreeNode[]
}

export interface SystemResponse {
  root: BodySummary
  home_world: BodyDetail
  body_count: number
  tree: BodyTreeNode[]
}

export interface DestinationEntry {
  body: BodySummary
  transfer_dv: number
}

export interface RouteRequest {
  destination: string | null
  moon: string | null
}

export interface DvStepResponse {
  label: string
  dv: number
  cumulative: number
  note: string
}

export interface RouteResponse {
  steps: DvStepResponse[]
  total_powered: number
  total_aerobrake: number | null
}

// --- Upload types ---

export interface UploadResponse {
  bodies_added: string[]
  count: number
}

// --- Atmosphere profile ---

export interface AtmoProfileResponse {
  altitude: number[]
  pressure: number[]
  temperature: number[]
  density: number[]
}

// --- Health ---

export interface HealthResponse {
  status: string
}
