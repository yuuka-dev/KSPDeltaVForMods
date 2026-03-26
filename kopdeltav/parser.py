"""Kopernicus ConfigNode parser for KSP1 planet pack mods.

Kopernicus の ConfigNode 形式をパースし、CelestialBody を抽出する。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from kopdeltav.models import (
    Atmosphere,
    CelestialBody,
    CurveKey,
    OrbitalElements,
)

logger = logging.getLogger(__name__)

# Modifier characters that may prefix node names in ModuleManager syntax.
_MODIFIER_CHARS = frozenset("@!+-%")

# Pattern for inline delete directives like `!Body[Kerbin]{}`
_DELETE_DIRECTIVE_RE = re.compile(r"^!(\w+)\[.*?\]\s*\{\s*\}\s*$")

# Pattern that matches a node header: optional modifiers, name, optional MM filter, then `{`.
# Examples:  `Body {`, `@Kopernicus:AFTER[Kopernicus] {`, `Properties`
_NODE_OPEN_RE = re.compile(
    r"^"
    r"([!@+\-%]?)"  # optional single modifier prefix
    r"(\w+)"  # node name
    r"([^\{]*)"  # optional MM filter / annotations (ignored)
    r"$"
)


@dataclass
class ConfigNode:
    """A generic KSP ConfigNode tree.

    KSP ConfigNode の汎用ツリー構造。

    Attributes:
        name: Node name with modifier characters stripped.
        values: Ordered list of (key, value) pairs contained in this node.
        children: Ordered list of child ConfigNode instances.
    """

    name: str
    values: list[tuple[str, str]] = field(default_factory=list)
    children: list[ConfigNode] = field(default_factory=list)

    def get_value(self, key: str, default: str | None = None) -> str | None:
        """Return the first value matching *key*, or *default*.

        指定キーの最初の値を返す。見つからなければ default。

        Args:
            key: The key name to look up (case-sensitive).
            default: Value to return when key is not found.

        Returns:
            The value string, or *default*.
        """
        for k, v in self.values:
            if k == key:
                return v
        return default

    def get_values(self, key: str) -> list[str]:
        """Return all values matching *key*.

        指定キーの全ての値をリストで返す。

        Args:
            key: The key name to look up (case-sensitive).

        Returns:
            List of value strings (may be empty).
        """
        return [v for k, v in self.values if k == key]

    def get_child(self, name: str) -> ConfigNode | None:
        """Return the first child node with the given *name*, or None.

        指定名の最初の子ノードを返す。

        Args:
            name: Child node name (case-sensitive).

        Returns:
            The matching ConfigNode, or None.
        """
        for child in self.children:
            if child.name == name:
                return child
        return None


# ---------------------------------------------------------------------------
# Low-level ConfigNode text parser
# ---------------------------------------------------------------------------


def _strip_comments(line: str) -> str:
    """Remove ``//`` comments from a line, respecting no quoting rules.

    行内の ``//`` コメントを除去する。

    KSP ConfigNode has no string quoting, so ``//`` always starts a comment.

    Args:
        line: A single line of text.

    Returns:
        The line with trailing comment removed and stripped of whitespace.
    """
    idx = line.find("//")
    if idx != -1:
        line = line[:idx]
    return line.strip()


def parse_config_text(source: str) -> list[ConfigNode]:
    """Parse raw ConfigNode text into a list of top-level ConfigNode trees.

    ConfigNode テキストをパースし、トップレベルのノードツリーをリストで返す。

    The parser handles:
    - Mixed tab/space indentation
    - Empty lines and ``//`` comments
    - Modifier prefixes (``@``, ``!``, ``+``, ``-``, ``%``) which are stripped
    - Inline delete directives like ``!Body[Kerbin]{}`` which are skipped
    - Values containing spaces (e.g. ``name = North Pole``)
    - Scientific notation in values (e.g. ``1.10444E+02``)

    Args:
        source: The full text content of a ``.cfg`` file.

    Returns:
        A list of top-level ConfigNode trees.
    """
    lines = source.splitlines()
    top_level: list[ConfigNode] = []
    stack: list[ConfigNode] = []
    # `pending_name` holds the name of a node whose opening `{` has not yet
    # been seen (it appears on the *next* line).
    pending_name: str | None = None

    for line_no, raw_line in enumerate(lines, start=1):
        line = _strip_comments(raw_line)
        if not line:
            continue

        # --- Inline delete directive: `!Body[Kerbin]{}` -----------------------
        if _DELETE_DIRECTIVE_RE.match(line):
            logger.debug("Line %d: skipping delete directive: %s", line_no, line)
            continue

        # --- Closing brace -----------------------------------------------------
        if line == "}":
            if not stack:
                logger.warning("Line %d: unexpected '}' with no open node", line_no)
                continue
            closed = stack.pop()
            if stack:
                stack[-1].children.append(closed)
            else:
                top_level.append(closed)
            continue

        # --- Opening brace (alone on a line) -----------------------------------
        if line == "{":
            name = pending_name if pending_name is not None else ""
            pending_name = None
            stack.append(ConfigNode(name=name))
            continue

        # --- Line contains `{` — could be "Name {" or "Name{" -----------------
        if "{" in line:
            before, _, after = line.partition("{")
            before = before.strip()

            # Determine node name from text before `{`
            node_name = _clean_node_name(before) if before else (pending_name or "")
            pending_name = None

            node = ConfigNode(name=node_name)

            # If `}` also present on the same line (empty node like `Name{}`)
            after = after.strip()
            if after.startswith("}"):
                # Empty inline node — attach and move on
                if stack:
                    stack[-1].children.append(node)
                else:
                    top_level.append(node)
                continue

            stack.append(node)
            # Process remaining text after `{` if any (unusual but safe)
            continue

        # --- key = value -------------------------------------------------------
        if "=" in line:
            # If there's a pending node name that hasn't been opened yet this is
            # unusual; treat the pending name as a value-less entry and continue.
            if pending_name is not None:
                logger.warning(
                    "Line %d: pending node name '%s' followed by key=value; "
                    "discarding pending name",
                    line_no,
                    pending_name,
                )
                pending_name = None

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if stack:
                stack[-1].values.append((key, value))
            else:
                logger.warning(
                    "Line %d: key=value '%s' outside any node",
                    line_no,
                    line,
                )
            continue

        # --- Bare identifier (potential node name on its own line) -------------
        # This handles the case where a node name appears on one line and `{` on
        # the next.
        if pending_name is not None:
            # Two consecutive bare identifiers — store the first as an
            # orphan value entry and keep the second as pending.
            logger.warning(
                "Line %d: discarding orphan identifier '%s'",
                line_no,
                pending_name,
            )
        pending_name = _clean_node_name(line)

    # If the stack is not empty, the file ended with unclosed nodes.
    if stack:
        logger.warning(
            "Unexpected end of input: %d unclosed node(s). Closing them automatically.",
            len(stack),
        )
        while stack:
            closed = stack.pop()
            if stack:
                stack[-1].children.append(closed)
            else:
                top_level.append(closed)

    return top_level


def _clean_node_name(raw: str) -> str:
    """Strip modifier prefixes and MM filter annotations from a node name.

    修飾子プレフィクスと MM フィルタをノード名から除去する。

    Args:
        raw: The raw string before the opening brace (already stripped).

    Returns:
        A clean node name string.
    """
    raw = raw.strip()
    # Strip leading modifier character(s)
    while raw and raw[0] in _MODIFIER_CHARS:
        raw = raw[1:]
    # Remove MM filter annotations like `:AFTER[Kopernicus]`
    colon_idx = raw.find(":")
    if colon_idx != -1:
        raw = raw[:colon_idx]
    # Remove bracket expressions like `[Kerbin]`
    bracket_idx = raw.find("[")
    if bracket_idx != -1:
        raw = raw[:bracket_idx]
    return raw.strip()


# ---------------------------------------------------------------------------
# Curve key parser
# ---------------------------------------------------------------------------


def _parse_curve_key(raw_value: str, line_context: str = "") -> CurveKey | None:
    """Parse a single curve key value string into a CurveKey.

    カーブキー文字列を CurveKey に変換する。

    Expected formats:
    - ``position value``
    - ``position value inTangent``
    - ``position value inTangent outTangent``

    When *outTangent* is omitted, it defaults to *inTangent*.
    When *inTangent* is also omitted, both default to 0.

    Args:
        raw_value: The value portion of ``key = ...``.
        line_context: Optional description for log messages.

    Returns:
        A CurveKey instance, or None if parsing fails.
    """
    parts = raw_value.split()
    if len(parts) < 2:
        logger.warning("Malformed curve key (need >= 2 values): '%s' %s", raw_value, line_context)
        return None
    try:
        position = float(parts[0])
        value = float(parts[1])
        in_tangent = float(parts[2]) if len(parts) >= 3 else 0.0
        out_tangent = float(parts[3]) if len(parts) >= 4 else in_tangent
        return CurveKey(
            position=position,
            value=value,
            in_tangent=in_tangent,
            out_tangent=out_tangent,
        )
    except (ValueError, IndexError) as exc:
        logger.warning("Failed to parse curve key '%s': %s %s", raw_value, exc, line_context)
        return None


# ---------------------------------------------------------------------------
# High-level domain-specific body extractor
# ---------------------------------------------------------------------------


def _parse_float(value: str | None, default: float = 0.0) -> float:
    """Safely convert a string to float, returning *default* on failure.

    文字列を float に変換する。失敗時は default を返す。

    Args:
        value: String value to convert, or None.
        default: Default value when conversion fails or value is None.

    Returns:
        The parsed float or *default*.
    """
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Cannot convert '%s' to float; using default %s", value, default)
        return default


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """Safely convert a string to bool (case-insensitive), returning *default*.

    文字列を bool に変換する。

    Args:
        value: String value (``True``/``False``), or None.
        default: Default value when conversion fails or value is None.

    Returns:
        The parsed bool or *default*.
    """
    if value is None:
        return default
    return value.strip().lower() == "true"


def _extract_curve_keys(node: ConfigNode) -> list[CurveKey]:
    """Extract and sort CurveKey entries from a curve node.

    カーブノードから CurveKey をリストとして抽出しソートする。

    Args:
        node: A ConfigNode representing a curve (e.g. ``temperatureCurve``).

    Returns:
        A list of CurveKey sorted ascending by position.
    """
    keys: list[CurveKey] = []
    for raw_val in node.get_values("key"):
        ck = _parse_curve_key(raw_val, line_context=f"in {node.name}")
        if ck is not None:
            keys.append(ck)
    keys.sort(key=lambda k: k.position)
    return keys


def _extract_atmosphere(body_node: ConfigNode) -> Atmosphere | None:
    """Extract Atmosphere data from a Body node, if present and enabled.

    Body ノードから大気情報を抽出する。無効または存在しない場合 None。

    Args:
        body_node: The Body-level ConfigNode.

    Returns:
        An Atmosphere instance, or None.
    """
    atmo_node = body_node.get_child("Atmosphere")
    if atmo_node is None:
        return None

    enabled = _parse_bool(atmo_node.get_value("enabled"), default=False)
    if not enabled:
        logger.debug("Atmosphere node found but enabled=False; skipping")
        return None

    altitude = _parse_float(atmo_node.get_value("altitude"))
    adiabatic_index = _parse_float(atmo_node.get_value("adiabaticIndex"), default=1.4)
    molar_mass = _parse_float(atmo_node.get_value("atmosphereMolarMass"), default=0.02897)
    temperature_sea_level = _parse_float(atmo_node.get_value("temperatureSeaLevel"))
    pressure_sea_level = _parse_float(atmo_node.get_value("staticPressureASL"))

    # Extract curves
    temp_curve_node = atmo_node.get_child("temperatureCurve")
    temperature_curve = _extract_curve_keys(temp_curve_node) if temp_curve_node else []

    press_curve_node = atmo_node.get_child("pressureCurve")
    pressure_curve = _extract_curve_keys(press_curve_node) if press_curve_node else []

    return Atmosphere(
        atmosphere_depth=altitude,
        pressure_curve=pressure_curve,
        temperature_curve=temperature_curve,
        molar_mass=molar_mass,
        adiabatic_index=adiabatic_index,
        pressure_at_sea_level=pressure_sea_level,
        temperature_at_sea_level=temperature_sea_level,
    )


def _extract_orbit(body_node: ConfigNode) -> OrbitalElements | None:
    """Extract OrbitalElements from a Body node, if an Orbit child exists.

    Body ノードから軌道要素を抽出する。Orbit がなければ None (恒星)。

    Args:
        body_node: The Body-level ConfigNode.

    Returns:
        An OrbitalElements instance, or None for root stars with no orbit.
    """
    orbit_node = body_node.get_child("Orbit")
    if orbit_node is None:
        return None

    return OrbitalElements(
        semi_major_axis=_parse_float(orbit_node.get_value("semiMajorAxis")),
        eccentricity=_parse_float(orbit_node.get_value("eccentricity")),
        inclination=_parse_float(orbit_node.get_value("inclination")),
        argument_of_periapsis=_parse_float(orbit_node.get_value("argumentOfPeriapsis")),
        longitude_of_ascending_node=_parse_float(orbit_node.get_value("longitudeOfAscendingNode")),
        mean_anomaly_at_epoch=_parse_float(orbit_node.get_value("meanAnomalyAtEpoch")),
        epoch=_parse_float(orbit_node.get_value("epoch")),
    )


def _extract_has_ocean(body_node: ConfigNode) -> bool:
    """Determine whether a body has an ocean.

    天体が海を持つか判定する。

    Args:
        body_node: The Body-level ConfigNode.

    Returns:
        True if an Ocean child node exists with ``ocean = True``.
    """
    ocean_node = body_node.get_child("Ocean")
    if ocean_node is None:
        return False
    return _parse_bool(ocean_node.get_value("ocean"), default=False)


def _resolve_display_name(
    properties: ConfigNode | None,
    body_name: str,
    source_filename: str = "",
) -> str:
    """Resolve display name, falling back to filename then body name for #LOC_ tags.

    displayName を解決する。#LOC_ タグの場合はファイル名、次に name にフォールバック。

    Args:
        properties: The Properties child ConfigNode (may be None).
        body_name: The internal body name used as fallback.
        source_filename: Source .cfg filename (without extension) as preferred fallback.

    Returns:
        The resolved display name string.
    """
    if properties is None:
        return source_filename or body_name
    display_name = properties.get_value("displayName")
    if display_name is None or display_name.startswith("#LOC_"):
        return source_filename or body_name
    return display_name


def _extract_body(body_node: ConfigNode, source_filename: str = "") -> CelestialBody | None:
    """Extract a CelestialBody from a Body-level ConfigNode.

    Body ノードから CelestialBody を抽出する。

    Skips nodes that lack a ``name`` value. Warns on parsing issues but
    never raises exceptions.

    Args:
        body_node: A ConfigNode with name ``"Body"``.
        source_filename: Source .cfg filename (without extension) for display name fallback.

    Returns:
        A CelestialBody instance, or None if the node is malformed.
    """
    name = body_node.get_value("name")
    if name is None:
        logger.warning("Body node has no 'name' value; skipping")
        return None

    properties = body_node.get_child("Properties")

    radius = _parse_float(
        properties.get_value("radius") if properties else None,
        default=600000.0,
    )
    gee_asl = _parse_float(
        properties.get_value("geeASL") if properties else None,
        default=1.0,
    )
    rotational_period = _parse_float(
        properties.get_value("rotationPeriod") if properties else None,
        default=0.0,
    )
    display_name = _resolve_display_name(properties, name, source_filename)

    is_home_world = _parse_bool(
        properties.get_value("isHomeWorld") if properties else None,
        default=False,
    )

    orbit_node = body_node.get_child("Orbit")
    reference_body_name = ""
    if orbit_node is not None:
        raw_ref = orbit_node.get_value("referenceBody")
        if raw_ref is not None:
            reference_body_name = raw_ref.strip()

    try:
        atmosphere = _extract_atmosphere(body_node)
    except Exception as exc:
        logger.warning("Failed to parse Atmosphere for '%s': %s", name, exc)
        atmosphere = None

    try:
        orbit = _extract_orbit(body_node)
    except Exception as exc:
        logger.warning("Failed to parse Orbit for '%s': %s", name, exc)
        orbit = None

    has_ocean = _extract_has_ocean(body_node)

    try:
        return CelestialBody(
            name=name,
            radius=radius,
            gee_asl=gee_asl,
            has_ocean=has_ocean,
            atmosphere=atmosphere,
            orbit=orbit,
            rotational_period=rotational_period,
            display_name=display_name,
            is_home_world=is_home_world,
            reference_body_name=reference_body_name,
        )
    except Exception as exc:
        logger.warning("Failed to construct CelestialBody '%s': %s", name, exc)
        return None


def parse_bodies(source: str, source_filename: str = "") -> list[CelestialBody]:
    """Parse Kopernicus config text and extract CelestialBody objects.

    Kopernicus 設定テキストをパースし、CelestialBody のリストを返す。

    This is the main entry point. It parses the raw ConfigNode text, then
    walks the tree to find all ``Body`` nodes and converts them into
    CelestialBody instances.

    Delete directives (``!Body[Name]{}``) are skipped during ConfigNode
    parsing. Malformed sections are skipped with a warning — the parser
    never crashes on invalid input.

    Args:
        source: The full text content of a Kopernicus ``.cfg`` file.
        source_filename: Source filename (without extension) used as display
            name fallback when ``displayName`` is a ``#LOC_`` tag.

    Returns:
        A list of CelestialBody objects found in the config. May be empty
        if no valid bodies are found.
    """
    top_nodes = parse_config_text(source)
    bodies: list[CelestialBody] = []

    def _walk(nodes: list[ConfigNode]) -> None:
        """Recursively walk ConfigNode trees to find Body nodes.

        ConfigNode ツリーを再帰的に走査して Body ノードを探す。

        Args:
            nodes: List of ConfigNode instances to search.
        """
        for node in nodes:
            if node.name == "Body":
                body = _extract_body(node, source_filename=source_filename)
                if body is not None:
                    bodies.append(body)
            else:
                # Body nodes can be nested inside wrapper nodes like
                # `@Kopernicus:AFTER[Kopernicus] { Body { ... } }`
                _walk(node.children)

    _walk(top_nodes)
    return bodies
