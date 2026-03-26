"""FastAPI REST API for KSPDeltaVForMods.

KSPDeltaVForMods の REST API。天体データ管理・ΔV 計算エンドポイントを提供する。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from kopdeltav.calculator import (
    calculate_hohmann,
    calculate_launch,
    calculate_tsiolkovsky,
    compute_route,
    density_at_altitude,
    landing_dv,
    surface_density,
)
from kopdeltav.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, get_text
from kopdeltav.models import CelestialBody, hermite_interp
from kopdeltav.parser import parse_bodies
from kopdeltav.system import CelestialSystem, scan_configs, sort_by_transfer_dv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory body store
# ---------------------------------------------------------------------------

_bodies: dict[str, CelestialBody] = {}
_system: CelestialSystem | None = None

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class BodySummary(BaseModel):
    """Summary of a celestial body for list endpoints.

    天体一覧用サマリー。
    """

    name: str
    display_name: str
    radius: float
    gee_asl: float
    has_atmosphere: bool
    has_ocean: bool


class OrbitResponse(BaseModel):
    """Orbital elements response.

    軌道要素レスポンス。
    """

    semi_major_axis: float
    eccentricity: float
    inclination: float
    argument_of_periapsis: float
    longitude_of_ascending_node: float
    mean_anomaly_at_epoch: float
    epoch: float


class AtmosphereResponse(BaseModel):
    """Atmosphere parameters response.

    大気パラメータレスポンス。
    """

    atmosphere_depth: float
    pressure_at_sea_level: float
    temperature_at_sea_level: float
    molar_mass: float
    adiabatic_index: float
    sea_level_density: float | None = None


class BodyDetail(BaseModel):
    """Detailed celestial body response.

    天体詳細レスポンス。
    """

    name: str
    display_name: str
    radius: float
    gee_asl: float
    mu: float
    has_ocean: bool
    rotational_period: float
    soi: float
    atmosphere: AtmosphereResponse | None = None
    orbit: OrbitResponse | None = None


class LaunchRequest(BaseModel):
    """Request for launch-to-orbit ΔV calculation.

    低軌道投入ΔV計算リクエスト。
    """

    body_name: str
    target_altitude: float = Field(ge=0, description="Target altitude above surface [m]")


class LaunchResponse(BaseModel):
    """Response for launch-to-orbit ΔV calculation.

    低軌道投入ΔV計算レスポンス。
    """

    orbital_velocity: float
    gravity_loss: float
    drag_loss: float
    total_ideal: float
    total_rocket: float
    jet_savings: float
    total_with_jets: float


class HohmannRequest(BaseModel):
    """Request for Hohmann transfer calculation.

    ホーマン遷移計算リクエスト。
    """

    body_name: str
    parking_altitude: float = Field(ge=0, description="Parking orbit altitude [m]")
    target_sma: float = Field(gt=0, description="Target semi-major axis [m]")


class HohmannResponse(BaseModel):
    """Response for Hohmann transfer calculation.

    ホーマン遷移計算レスポンス。
    """

    departure_dv: float
    arrival_dv: float
    total_dv: float
    transfer_time: float


class TsiolkovskyRequest(BaseModel):
    """Request for Tsiolkovsky rocket equation.

    ツィオルコフスキー方程式リクエスト。
    """

    delta_v: float = Field(ge=0, description="Required delta-v [m/s]")
    isp: float = Field(gt=0, description="Specific impulse [s]")
    wet_mass: float = Field(gt=0, description="Total wet mass [kg]")


class TsiolkovskyResponse(BaseModel):
    """Response for Tsiolkovsky rocket equation.

    ツィオルコフスキー方程式レスポンス。
    """

    mass_ratio: float
    fuel_fraction: float
    dry_mass: float
    fuel_mass: float


class ManualBodyRequest(BaseModel):
    """Request to manually add a celestial body.

    天体の手動追加リクエスト。
    """

    name: str
    radius: float = Field(gt=0)
    gee_asl: float = Field(gt=0)
    has_ocean: bool = False
    rotational_period: float = 0.0
    display_name: str | None = None


class AtmoProfileResponse(BaseModel):
    """Atmosphere profile at sampled altitudes.

    高度ごとの大気プロファイル。
    """

    altitude: list[float]
    pressure: list[float]
    temperature: list[float]
    density: list[float]


class UploadResponse(BaseModel):
    """Response for config file upload.

    設定ファイルアップロードのレスポンス。
    """

    bodies_added: list[str]
    count: int


class ScanRequest(BaseModel):
    """Request to scan a GameData directory for Kopernicus configs.

    GameData ディレクトリをスキャンするリクエスト。
    """

    gamedata_path: str
    exclude_dirs: list[str] = ["Kopernicus"]


class BodyTreeNode(BaseModel):
    """A node in the celestial body hierarchy tree.

    天体ツリーの単一ノード。
    """

    name: str
    display_name: str
    children: list[BodyTreeNode]


BodyTreeNode.model_rebuild()


class SystemResponse(BaseModel):
    """Response representing the entire celestial system.

    惑星系全体のレスポンス。
    """

    root: BodySummary
    home_world: BodyDetail
    body_count: int
    tree: list[BodyTreeNode]


class DestinationEntry(BaseModel):
    """A destination body with its transfer ΔV from the home world.

    ホームワールドからの遷移ΔV付き目的地天体。
    """

    body: BodySummary
    transfer_dv: float


class RouteRequest(BaseModel):
    """Request for a ΔV route calculation.

    ΔVルート計算リクエスト。
    """

    destination: str | None = None
    moon: str | None = None


class DvStepResponse(BaseModel):
    """A single maneuver step in a ΔV route.

    ΔVルートの1マニューバステップ。
    """

    label: str
    dv: float
    cumulative: float
    note: str = ""


class RouteResponse(BaseModel):
    """Full ΔV route response.

    ΔVルート全体のレスポンス。
    """

    steps: list[DvStepResponse]
    total_powered: float
    total_aerobrake: float | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_lang(request: Request, lang: str | None) -> str:
    """Resolve language from query parameter or Accept-Language header.

    クエリパラメータまたは Accept-Language ヘッダーから言語を解決する。

    Args:
        request: The incoming HTTP request.
        lang: Explicit language query parameter, or None.

    Returns:
        Resolved language code.
    """
    if lang is not None and lang in SUPPORTED_LANGUAGES:
        return lang
    accept = request.headers.get("accept-language", "")
    for supported in SUPPORTED_LANGUAGES:
        if supported in accept:
            return supported
    return DEFAULT_LANGUAGE


def _get_body(name: str, lang: str) -> CelestialBody:
    """Retrieve a body from the store or raise 404.

    ストアから天体を取得する。見つからなければ 404。

    Args:
        name: Internal body name.
        lang: Language code for error messages.

    Returns:
        The CelestialBody instance.

    Raises:
        HTTPException: If the body is not found (404).
    """
    body = _bodies.get(name)
    if body is None:
        msg = get_text("error.no_bodies", lang)
        raise HTTPException(status_code=404, detail=f"{msg}: {name}")
    return body


def _body_to_summary(body: CelestialBody) -> BodySummary:
    """Convert a CelestialBody to a BodySummary.

    CelestialBody を BodySummary に変換する。

    Args:
        body: The source celestial body.

    Returns:
        A BodySummary instance.
    """
    return BodySummary(
        name=body.name,
        display_name=body.display_name,
        radius=body.radius,
        gee_asl=body.gee_asl,
        has_atmosphere=body.atmosphere is not None,
        has_ocean=body.has_ocean,
    )


def _body_to_detail(body: CelestialBody) -> BodyDetail:
    """Convert a CelestialBody to a BodyDetail.

    CelestialBody を BodyDetail に変換する。

    Args:
        body: The source celestial body.

    Returns:
        A BodyDetail instance.
    """
    atmo_resp: AtmosphereResponse | None = None
    if body.atmosphere is not None:
        atmo = body.atmosphere
        rho = surface_density(body)
        atmo_resp = AtmosphereResponse(
            atmosphere_depth=atmo.atmosphere_depth,
            pressure_at_sea_level=atmo.pressure_at_sea_level,
            temperature_at_sea_level=atmo.temperature_at_sea_level,
            molar_mass=atmo.molar_mass,
            adiabatic_index=atmo.adiabatic_index,
            sea_level_density=rho,
        )

    orbit_resp: OrbitResponse | None = None
    if body.orbit is not None:
        orb = body.orbit
        orbit_resp = OrbitResponse(
            semi_major_axis=orb.semi_major_axis,
            eccentricity=orb.eccentricity,
            inclination=orb.inclination,
            argument_of_periapsis=orb.argument_of_periapsis,
            longitude_of_ascending_node=orb.longitude_of_ascending_node,
            mean_anomaly_at_epoch=orb.mean_anomaly_at_epoch,
            epoch=orb.epoch,
        )

    return BodyDetail(
        name=body.name,
        display_name=body.display_name,
        radius=body.radius,
        gee_asl=body.gee_asl,
        mu=body.mu,
        has_ocean=body.has_ocean,
        rotational_period=body.rotational_period,
        soi=body.soi,
        atmosphere=atmo_resp,
        orbit=orbit_resp,
    )


def _require_system() -> CelestialSystem:
    """Return the loaded CelestialSystem or raise 404.

    ロード済み CelestialSystem を返す。未ロードの場合は 404 を送出。

    Returns:
        The current CelestialSystem.

    Raises:
        HTTPException: If no system has been loaded yet (404).
    """
    if _system is None:
        raise HTTPException(
            status_code=404,
            detail="No system loaded. Call POST /scan first.",
        )
    return _system


def _body_to_tree_node(body: CelestialBody) -> BodyTreeNode:
    """Recursively convert a CelestialBody to a BodyTreeNode.

    CelestialBody を再帰的に BodyTreeNode へ変換する。

    Args:
        body: The source celestial body.

    Returns:
        A BodyTreeNode representing the body and its subtree.
    """
    return BodyTreeNode(
        name=body.name,
        display_name=body.display_name,
        children=[_body_to_tree_node(child) for child in body.children],
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="KSPDeltaVForMods",
    description="Delta-V calculator for KSP1 planet pack mods",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/bodies", response_model=list[BodySummary])
async def list_bodies(
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> list[BodySummary]:
    """List all registered celestial bodies.

    登録済み天体一覧を返す。
    """
    _resolve_lang(request, lang)  # validate lang for future use
    return [_body_to_summary(b) for b in _bodies.values()]


@app.get("/bodies/{name}", response_model=BodyDetail)
async def get_body_detail(
    name: str,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> BodyDetail:
    """Get detailed information about a celestial body.

    天体の詳細情報を返す。
    """
    resolved_lang = _resolve_lang(request, lang)
    body = _get_body(name, resolved_lang)
    return _body_to_detail(body)


@app.post("/bodies/manual", response_model=BodyDetail, status_code=201)
async def add_manual_body(
    req: ManualBodyRequest,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> BodyDetail:
    """Manually add a celestial body.

    天体を手動で追加する。
    """
    _resolve_lang(request, lang)
    body = CelestialBody(
        name=req.name,
        radius=req.radius,
        gee_asl=req.gee_asl,
        has_ocean=req.has_ocean,
        atmosphere=None,
        orbit=None,
        rotational_period=req.rotational_period,
        display_name=req.display_name if req.display_name is not None else req.name,
    )
    _bodies[body.name] = body
    return _body_to_detail(body)


@app.post("/upload-config", response_model=UploadResponse)
async def upload_config(
    file: UploadFile,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> UploadResponse:
    """Upload a Kopernicus .cfg file and register parsed bodies.

    Kopernicus .cfg ファイルをアップロードしてパース結果を登録する。
    """
    resolved_lang = _resolve_lang(request, lang)
    content = await file.read()
    try:
        source = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail=get_text("error.parse_error", resolved_lang),
        ) from None

    bodies = parse_bodies(source)
    if not bodies:
        raise HTTPException(
            status_code=400,
            detail=get_text("error.no_bodies", resolved_lang),
        )

    added: list[str] = []
    for body in bodies:
        _bodies[body.name] = body
        added.append(body.name)

    return UploadResponse(bodies_added=added, count=len(added))


@app.post("/calc/launch", response_model=LaunchResponse)
async def calc_launch(
    req: LaunchRequest,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> LaunchResponse:
    """Calculate launch-to-orbit delta-v.

    低軌道投入ΔVを計算する。
    """
    resolved_lang = _resolve_lang(request, lang)
    body = _get_body(req.body_name, resolved_lang)
    try:
        result = calculate_launch(body, req.target_altitude)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return LaunchResponse(
        orbital_velocity=result.orbital_velocity,
        gravity_loss=result.gravity_loss,
        drag_loss=result.drag_loss,
        total_ideal=result.total_ideal,
        total_rocket=result.total_rocket,
        jet_savings=result.jet_savings,
        total_with_jets=result.total_with_jets,
    )


@app.post("/calc/hohmann", response_model=HohmannResponse)
async def calc_hohmann(
    req: HohmannRequest,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> HohmannResponse:
    """Calculate Hohmann transfer delta-v.

    ホーマン遷移ΔVを計算する。
    """
    resolved_lang = _resolve_lang(request, lang)
    body = _get_body(req.body_name, resolved_lang)
    try:
        result = calculate_hohmann(body, req.parking_altitude, req.target_sma)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return HohmannResponse(
        departure_dv=result.departure_dv,
        arrival_dv=result.arrival_dv,
        total_dv=result.total_dv,
        transfer_time=result.transfer_time,
    )


@app.post("/calc/tsiolkovsky", response_model=TsiolkovskyResponse)
async def calc_tsiolkovsky(
    req: TsiolkovskyRequest,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
) -> TsiolkovskyResponse:
    """Calculate Tsiolkovsky rocket equation.

    ツィオルコフスキーの式で質量比を計算する。
    """
    _resolve_lang(request, lang)
    try:
        result = calculate_tsiolkovsky(req.delta_v, req.isp, req.wet_mass)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return TsiolkovskyResponse(
        mass_ratio=result.mass_ratio,
        fuel_fraction=result.fuel_fraction,
        dry_mass=result.dry_mass,
        fuel_mass=result.fuel_mass,
    )


@app.get("/atmo-profile/{name}", response_model=AtmoProfileResponse)
async def get_atmo_profile(
    name: str,
    request: Request,
    lang: Annotated[str | None, Query(description="Language code (ja/en)")] = None,
    steps: Annotated[int, Query(ge=10, le=500, description="Number of altitude steps")] = 100,
) -> AtmoProfileResponse:
    """Get atmosphere profile sampled at regular altitude intervals.

    一定間隔の高度で大気プロファイルを取得する。
    """
    resolved_lang = _resolve_lang(request, lang)
    body = _get_body(name, resolved_lang)

    if body.atmosphere is None:
        raise HTTPException(
            status_code=400,
            detail=get_text("body.no_atmosphere", resolved_lang),
        )

    atmo = body.atmosphere
    max_alt = atmo.atmosphere_depth
    altitudes: list[float] = []
    pressures: list[float] = []
    temperatures: list[float] = []
    densities: list[float] = []

    for i in range(steps + 1):
        alt = max_alt * i / steps
        altitudes.append(alt)

        if atmo.pressure_curve:
            p = hermite_interp(atmo.pressure_curve, alt)
        else:
            p = atmo.pressure_at_sea_level if alt == 0.0 else 0.0
        pressures.append(p)

        if atmo.temperature_curve:
            t = hermite_interp(atmo.temperature_curve, alt)
        else:
            t = atmo.temperature_at_sea_level if alt == 0.0 else 0.0
        temperatures.append(t)

        rho = density_at_altitude(body, alt)
        densities.append(rho if rho is not None else 0.0)

    return AtmoProfileResponse(
        altitude=altitudes,
        pressure=pressures,
        temperature=temperatures,
        density=densities,
    )


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------


@app.post("/scan", response_model=UploadResponse)
async def scan_gamedata(req: ScanRequest) -> UploadResponse:
    """Scan a GameData directory for Kopernicus configs and build the system.

    GameData ディレクトリをスキャンして惑星系ツリーを構築する。

    Args:
        req: ScanRequest containing the path and optional exclusion list.

    Returns:
        UploadResponse listing discovered body names.

    Raises:
        HTTPException: 404 if the path does not exist or no configs are found.
        HTTPException: 422 if the system has no home world.
    """
    global _system

    gd_path = Path(req.gamedata_path)
    if not gd_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"GameData path not found: {req.gamedata_path}",
        )
    if not gd_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"GameData path is not a directory: {req.gamedata_path}",
        )

    exclude = frozenset(d.lower() for d in req.exclude_dirs)
    try:
        system = scan_configs(gd_path, exclude_dirs=exclude)
    except ValueError as exc:
        msg = str(exc)
        if "No celestial bodies" in msg or "not an existing directory" in msg:
            raise HTTPException(status_code=404, detail=msg) from None
        # No home world or build_tree failure → 422
        raise HTTPException(status_code=422, detail=msg) from None

    _system = system
    # Also populate _bodies for backward compatibility.
    _bodies.clear()
    for name, body in system.bodies.items():
        _bodies[name] = body

    added = list(system.bodies.keys())
    return UploadResponse(bodies_added=added, count=len(added))


@app.get("/system", response_model=SystemResponse)
async def get_system() -> SystemResponse:
    """Return the current celestial system tree.

    現在の惑星系ツリーを返す。

    Returns:
        SystemResponse with root, home world, body count, and tree.

    Raises:
        HTTPException: 404 if no system has been loaded.
    """
    system = _require_system()
    root_node = _body_to_tree_node(system.root)
    return SystemResponse(
        root=_body_to_summary(system.root),
        home_world=_body_to_detail(system.home_world),
        body_count=len(system.bodies),
        tree=[root_node],
    )


@app.get("/system/home", response_model=BodyDetail)
async def get_system_home() -> BodyDetail:
    """Return the home world detail.

    ホームワールドの詳細を返す。

    Returns:
        BodyDetail of the home world.

    Raises:
        HTTPException: 404 if no system has been loaded.
    """
    system = _require_system()
    return _body_to_detail(system.home_world)


@app.get("/system/destinations", response_model=list[DestinationEntry])
async def get_system_destinations() -> list[DestinationEntry]:
    """Return transfer destinations sorted by ΔV from the home world.

    ホームワールドからの遷移ΔV順に目的地一覧を返す。

    Returns:
        List of DestinationEntry sorted ascending by transfer_dv.

    Raises:
        HTTPException: 404 if no system has been loaded.
        HTTPException: 422 if the home world has no orbit or no parent.
    """
    system = _require_system()
    home = system.home_world
    if home.parent is None or home.orbit is None:
        raise HTTPException(
            status_code=422,
            detail=f"Home world '{home.name}' has no parent or no orbit; cannot compute transfers.",
        )
    siblings = list(home.parent.children)
    try:
        sorted_targets = sort_by_transfer_dv(home, siblings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return [
        DestinationEntry(body=_body_to_summary(body), transfer_dv=dv) for body, dv in sorted_targets
    ]


@app.post("/calc/route", response_model=RouteResponse)
async def calc_route(req: RouteRequest) -> RouteResponse:
    """Compute a ΔV route from the home world to an optional destination.

    ホームワールドから目的地までのΔVルートを計算する。

    Args:
        req: RouteRequest with optional destination and moon names.

    Returns:
        RouteResponse with step-by-step ΔV breakdown.

    Raises:
        HTTPException: 404 if no system is loaded or a body name is unknown.
        HTTPException: 422 if the destination/moon combo is invalid.
    """
    system = _require_system()

    destination_body = None
    if req.destination is not None:
        destination_body = system.bodies.get(req.destination)
        if destination_body is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown destination body: {req.destination}",
            )

    moon_body = None
    if req.moon is not None:
        if destination_body is None:
            raise HTTPException(
                status_code=422,
                detail="Cannot specify moon without a destination.",
            )
        moon_body = system.bodies.get(req.moon)
        if moon_body is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown moon body: {req.moon}",
            )

    try:
        steps = compute_route(system, destination=destination_body, moon=moon_body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    step_responses = [
        DvStepResponse(
            label=s.label,
            dv=s.dv,
            cumulative=s.cumulative,
            note=s.note,
        )
        for s in steps
    ]
    total_powered = steps[-1].cumulative if steps else 0.0

    # Determine aerobrake alternative: check landing step note for aerobrake info.
    total_aerobrake: float | None = None
    final_body = moon_body if moon_body is not None else destination_body
    if final_body is not None and final_body.atmosphere is not None:
        powered_dv, aerobrake_dv = landing_dv(final_body)
        if aerobrake_dv is not None:
            total_aerobrake = total_powered - powered_dv + aerobrake_dv

    return RouteResponse(
        steps=step_responses,
        total_powered=total_powered,
        total_aerobrake=total_aerobrake,
    )


@app.get("/bodies/{name}/moons", response_model=list[DestinationEntry])
async def get_body_moons(name: str) -> list[DestinationEntry]:
    """Return the moons of a body sorted by transfer ΔV.

    天体の衛星を遷移ΔV順にソートして返す。

    Args:
        name: Internal name of the parent body.

    Returns:
        List of DestinationEntry for each moon, sorted ascending by transfer_dv.

    Raises:
        HTTPException: 404 if no system is loaded or the body is unknown.
        HTTPException: 422 if the body has no orbit to compute transfers from.
    """
    system = _require_system()
    body = system.bodies.get(name)
    if body is None:
        raise HTTPException(status_code=404, detail=f"Unknown body: {name}")

    if not body.children:
        return []

    try:
        sorted_moons = sort_by_transfer_dv(body, list(body.children))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return [
        DestinationEntry(body=_body_to_summary(moon), transfer_dv=dv) for moon, dv in sorted_moons
    ]
