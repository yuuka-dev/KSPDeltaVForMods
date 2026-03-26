"""Celestial system tree construction and GameData config scanning.

天体ツリーの構築と GameData/ の .cfg ファイルスキャンを提供する。
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from kopdeltav.calculator import calculate_hohmann
from kopdeltav.models import CelestialBody
from kopdeltav.parser import parse_bodies

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CelestialSystem
# ---------------------------------------------------------------------------


@dataclass
class CelestialSystem:
    """A fully linked tree of celestial bodies parsed from a Kopernicus config.

    Kopernicus 設定からパースされた天体の完全なツリー構造。

    Attributes:
        root: The root star (top of the hierarchy, no parent).
        bodies: Flat name → body lookup dict for O(1) access.
        home_world: The body with ``is_home_world=True``.
    """

    root: CelestialBody
    bodies: dict[str, CelestialBody]
    home_world: CelestialBody


# ---------------------------------------------------------------------------
# Tree construction
# ---------------------------------------------------------------------------


def _body_completeness(body: CelestialBody) -> int:
    """Score how complete a body's data is, for deduplication priority.

    天体データの完全度をスコア化する(重複排除の優先度判定用)。

    Args:
        body: The body to score.

    Returns:
        Integer score (higher = more complete).
    """
    score = 0
    if body.is_home_world:
        score += 100
    if body.orbit is not None:
        score += 10
    if body.reference_body_name:
        score += 5
    if body.atmosphere is not None:
        score += 3
    if body.radius > 0:
        score += 1
    return score


def build_tree(bodies: list[CelestialBody]) -> CelestialSystem:
    """Build a parent/children tree from a flat list of bodies.

    フラットな天体リストから親子関係ツリーを構築する。

    Steps:
        1. Index all bodies by name.
        2. Link ``parent`` / ``children`` using ``reference_body_name``.
        3. Identify the root: body with no ``orbit`` (primary star); fallback
           is any body whose ``reference_body_name`` did not resolve.
        4. Identify ``home_world``: body with ``is_home_world=True``; when none
           is found, pick a reasonable fallback (preferring Kerbin-like / habitable
           bodies) and continue with a warning.
        5. Compute SOI for bodies where ``soi == 0``:
           ``SOI = a * (m_body / m_parent)^(2/5)`` using SMA and mu values.

    Args:
        bodies: Flat list of CelestialBody objects (e.g. from ``parse_bodies``).

    Returns:
        A fully linked :class:`CelestialSystem`.

    Raises:
        ValueError: If *bodies* is empty or no root can be identified.
    """
    if not bodies:
        raise ValueError("Cannot build tree from an empty body list")

    # Step 1: deduplicate by name, preferring the most complete version.
    # Priority: is_home_world > has orbit > has reference_body_name > first seen.
    index: dict[str, CelestialBody] = {}
    for body in bodies:
        existing = index.get(body.name)
        if existing is None:
            index[body.name] = body
        else:
            # Prefer the body with more complete data.
            if _body_completeness(body) > _body_completeness(existing):
                index[body.name] = body
                logger.debug(
                    "Dedup: replacing '%s' with more complete version",
                    body.name,
                )

    deduped = list(index.values())

    # Reset parent/children to avoid stale links.
    for body in deduped:
        body.parent = None
        body.children = []

    # Step 2: link parent/children; track bodies with unresolved parents.
    for body in deduped:
        ref = body.reference_body_name
        if not ref:
            continue
        parent = index.get(ref)
        if parent is None:
            logger.debug(
                "Body '%s' references unknown referenceBody '%s'",
                body.name,
                ref,
            )
        else:
            body.parent = parent
            if body not in parent.children:
                parent.children.append(body)

    # Step 3: find root.
    # Primary: body with no orbit AND no reference_body_name AND has children.
    root: CelestialBody | None = None
    candidates = [b for b in deduped if b.orbit is None and not b.reference_body_name]
    if candidates:
        # Prefer the one with children (actual star, not an orphan body).
        with_children = [b for b in candidates if b.children]
        root = with_children[0] if with_children else candidates[0]

    # Fallback: body with no parent link after tree construction.
    if root is None:
        orphans = [b for b in deduped if b.parent is None and b.children]
        if orphans:
            root = orphans[0]

    if root is None:
        root = deduped[0]
        logger.warning(
            "Cannot determine root; defaulting to first body '%s'",
            root.name,
        )

    # Step 4: home world.
    home_world: CelestialBody | None = None
    for body in deduped:
        if body.is_home_world:
            home_world = body
            break

    if home_world is None:
        # Many planet packs omit isHomeWorld. To keep interactive tools usable,
        # pick a fallback and mark it as home.
        def _home_score(b: CelestialBody) -> int:
            score = 0
            if b.name.strip().lower() == "kerbin":
                score += 100
            if b.has_ocean:
                score += 50
            if b.atmosphere is not None:
                score += 30
            if b.rotational_period > 0.0:
                score += 10
            if b.orbit is not None:
                score += 5
            if b.parent is not None:
                score += 2
            return score

        home_world = max(deduped, key=_home_score)
        home_world.is_home_world = True
        logger.warning(
            "No body declares isHomeWorld=True; falling back to '%s' as home world.",
            home_world.name,
        )

    # Step 5: compute SOI where soi == 0.
    for body in deduped:
        if body.soi == 0.0 and body.parent is not None and body.orbit is not None:
            a = body.orbit.semi_major_axis
            m_body = body.mu
            m_parent = body.parent.mu
            if m_parent > 0.0 and a > 0.0:
                body.soi = a * (m_body / m_parent) ** 0.4
                logger.debug(
                    "Computed SOI for '%s': %.3e m (a=%.3e, mu_ratio=%.6f)",
                    body.name,
                    body.soi,
                    a,
                    m_body / m_parent,
                )

    return CelestialSystem(root=root, bodies=index, home_world=home_world)


# ---------------------------------------------------------------------------
# Transfer ΔV sorting
# ---------------------------------------------------------------------------


def sort_by_transfer_dv(
    origin: CelestialBody,
    targets: list[CelestialBody],
) -> list[tuple[CelestialBody, float]]:
    """Sort target bodies by Hohmann transfer ΔV from origin, ascending.

    origin からのホーマン遷移 ΔV 昇順でターゲット天体をソートする。

    Both *origin* and every target in *targets* must orbit the same parent
    body.  The parent body's gravitational parameter (``mu``) is used as the
    central body for all Hohmann calculations.

    Targets whose orbit is ``None`` or whose SMA is not greater than the
    origin's parking orbit radius are skipped with a warning.

    Args:
        origin: The departure body. Must have a non-None ``orbit`` and a
            non-None ``parent``.
        targets: List of target bodies orbiting the same parent as *origin*.

    Returns:
        List of ``(body, total_dv)`` tuples sorted ascending by *total_dv*.
        Bodies that could not be evaluated are omitted.

    Raises:
        ValueError: If *origin* has no orbit or no parent.
    """
    if origin.orbit is None:
        raise ValueError(f"Origin body '{origin.name}' has no orbit")
    if origin.parent is None:
        raise ValueError(f"Origin body '{origin.name}' has no parent")

    parent = origin.parent

    results: list[tuple[CelestialBody, float]] = []
    for target in targets:
        if target is origin:
            continue
        if target.orbit is None:
            logger.warning(
                "Target '%s' has no orbit; skipping from transfer sort",
                target.name,
            )
            continue
        target_sma = target.orbit.semi_major_axis
        try:
            # Handle inner planets (target SMA < origin SMA) by swapping r1/r2.
            origin_sma = origin.orbit.semi_major_axis
            r1_alt = min(origin_sma, target_sma) - parent.radius
            r2_sma = max(origin_sma, target_sma)
            hohmann = calculate_hohmann(parent, r1_alt, r2_sma)
        except ValueError as exc:
            logger.warning(
                "Cannot compute Hohmann transfer to '%s': %s",
                target.name,
                exc,
            )
            continue
        results.append((target, hohmann.total_dv))

    results.sort(key=lambda pair: pair[1])
    return results


# ---------------------------------------------------------------------------
# GameData/ config scanner
# ---------------------------------------------------------------------------


def scan_configs(
    gamedata_path: Path,
    output_dir: Path | None = None,
    exclude_dirs: frozenset[str] = frozenset({"kopernicus"}),
) -> CelestialSystem:
    """Recursively scan a GameData/ directory for Kopernicus ``.cfg`` files.

    GameData/ ディレクトリを再帰スキャンし、Kopernicus 設定から天体ツリーを構築する。

    All ``.cfg`` files are read. Directories whose **lowercase** names appear
    in *exclude_dirs* are skipped entirely (default: ``{"kopernicus"}``).
    Files that yield no bodies are silently ignored.  If *output_dir* is
    provided, every successfully parsed ``.cfg`` is copied there (directory
    is created if it does not exist).

    Args:
        gamedata_path: Path to the ``GameData/`` directory.
        output_dir: Optional directory to copy valid ``.cfg`` files into.
        exclude_dirs: Set of directory names (lowercase) to skip during scan.

    Returns:
        A :class:`CelestialSystem` built from all bodies found.

    Raises:
        ValueError: If *gamedata_path* is not an existing directory, if no
            bodies are found across all scanned configs, or if
            :func:`build_tree` fails (e.g. no home world).
    """
    if not gamedata_path.is_dir():
        raise ValueError(f"gamedata_path is not an existing directory: {gamedata_path}")

    all_bodies: list[CelestialBody] = []
    valid_cfgs: list[Path] = []

    for cfg_path in _iter_cfgs(gamedata_path, exclude_dirs):
        try:
            source = cfg_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read '%s': %s", cfg_path, exc)
            continue

        bodies = parse_bodies(source, source_filename=cfg_path.stem)
        if not bodies:
            logger.debug("No bodies found in '%s'; skipping", cfg_path)
            continue

        logger.info("Found %d body/bodies in '%s'", len(bodies), cfg_path)
        all_bodies.extend(bodies)
        valid_cfgs.append(cfg_path)

    if not all_bodies:
        raise ValueError(f"No celestial bodies found under '{gamedata_path}'")

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for cfg_path in valid_cfgs:
            dest = output_dir / cfg_path.name
            try:
                shutil.copy2(cfg_path, dest)
                logger.debug("Copied '%s' → '%s'", cfg_path, dest)
            except OSError as exc:
                logger.warning("Cannot copy '%s' to '%s': %s", cfg_path, dest, exc)

    return build_tree(all_bodies)


def _iter_cfgs(directory: Path, exclude_dirs: frozenset[str]) -> list[Path]:
    """Recursively yield .cfg files under *directory*, skipping excluded dirs.

    ディレクトリ以下の .cfg ファイルをリストで返す。除外ディレクトリはスキップ。

    Args:
        directory: Root directory to scan.
        exclude_dirs: Lowercase directory names to skip.

    Returns:
        Sorted list of Path objects for all matching ``.cfg`` files.
    """
    results: list[Path] = []
    try:
        entries = sorted(directory.iterdir())
    except OSError as exc:
        logger.warning("Cannot list directory '%s': %s", directory, exc)
        return results

    for entry in entries:
        if entry.is_dir():
            if entry.name.lower() in exclude_dirs:
                logger.debug("Skipping excluded directory '%s'", entry)
                continue
            results.extend(_iter_cfgs(entry, exclude_dirs))
        elif entry.is_file() and entry.suffix.lower() == ".cfg":
            results.append(entry)

    return results
