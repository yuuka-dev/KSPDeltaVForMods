"""Tests for kopdeltav.system — tree construction and config scanning.

system モジュール(天体ツリー構築・設定スキャン)のテスト。
"""

from __future__ import annotations

from kopdeltav.models import CelestialBody, OrbitalElements
from kopdeltav.system import build_tree, is_barycenter, sort_by_transfer_dv

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_body(
    name: str,
    radius: float = 600_000.0,
    gee_asl: float = 1.0,
    reference_body_name: str = "",
    is_home_world: bool = False,
    orbit_sma: float = 0.0,
    rotational_period: float = 21_600.0,
) -> CelestialBody:
    """Create a minimal CelestialBody for testing.

    テスト用の最小限の CelestialBody を生成するヘルパー。

    Args:
        name: Body name.
        radius: Equatorial radius [m].
        gee_asl: Surface gravity in g.
        reference_body_name: Name of the parent body (Orbit.referenceBody).
        is_home_world: Whether this body is the home world.
        orbit_sma: Semi-major axis [m]. When 0, ``orbit`` is set to ``None``.
        rotational_period: Sidereal rotation period [s].

    Returns:
        A CelestialBody instance suitable for tree-building tests.
    """
    orbit: OrbitalElements | None = None
    if orbit_sma > 0.0:
        orbit = OrbitalElements(
            semi_major_axis=orbit_sma,
            eccentricity=0.0,
            inclination=0.0,
            argument_of_periapsis=0.0,
            longitude_of_ascending_node=0.0,
            mean_anomaly_at_epoch=0.0,
            epoch=0.0,
        )
    return CelestialBody(
        name=name,
        radius=radius,
        gee_asl=gee_asl,
        has_ocean=False,
        atmosphere=None,
        orbit=orbit,
        rotational_period=rotational_period,
        display_name=name,
        is_home_world=is_home_world,
        reference_body_name=reference_body_name,
    )


# ---------------------------------------------------------------------------
# TestBuildTree
# ---------------------------------------------------------------------------


class TestBuildTree:
    """Tests for build_tree()."""

    def test_single_star(self) -> None:
        """A single star with no orbit is the root and has no children."""
        star = _make_body("Star", is_home_world=True)
        system = build_tree([star])

        assert system.root is star
        assert star.children == []
        assert star.parent is None

    def test_star_and_planet(self) -> None:
        """A star + a planet with referenceBody are linked as parent/child."""
        star = _make_body("Star", is_home_world=False)
        planet = _make_body(
            "Planet",
            reference_body_name="Star",
            is_home_world=True,
            orbit_sma=13_599_840_256.0,
        )
        system = build_tree([star, planet])

        assert system.root is star
        assert planet.parent is star
        assert planet in star.children

    def test_planet_with_moon(self) -> None:
        """Three-body hierarchy: star → planet → moon."""
        star = _make_body("Star")
        planet = _make_body(
            "Planet",
            reference_body_name="Star",
            is_home_world=True,
            orbit_sma=13_599_840_256.0,
        )
        moon = _make_body(
            "Moon",
            radius=200_000.0,
            gee_asl=0.166,
            reference_body_name="Planet",
            orbit_sma=12_000_000.0,
        )
        build_tree([star, planet, moon])

        assert moon.parent is planet
        assert moon in planet.children
        assert planet.parent is star

    def test_parent_child_links(self) -> None:
        """Verify both .parent and .children are set correctly."""
        star = _make_body("Star")
        planet1 = _make_body(
            "Planet1",
            reference_body_name="Star",
            is_home_world=True,
            orbit_sma=10_000_000_000.0,
        )
        planet2 = _make_body(
            "Planet2",
            reference_body_name="Star",
            orbit_sma=20_000_000_000.0,
        )
        build_tree([star, planet1, planet2])

        assert planet1.parent is star
        assert planet2.parent is star
        assert planet1 in star.children
        assert planet2 in star.children

    def test_no_home_world_raises(self) -> None:
        """When no body has is_home_world=True, build_tree falls back with a warning."""
        star = _make_body("Star", is_home_world=False)
        system = build_tree([star])
        assert system.home_world is star
        assert system.home_world.is_home_world is True

    def test_root_identified_by_no_orbit(self) -> None:
        """Body with orbit=None (no Orbit node) is identified as root."""
        star = _make_body("Star", orbit_sma=0.0)  # orbit=None
        planet = _make_body(
            "Planet",
            reference_body_name="Star",
            is_home_world=True,
            orbit_sma=10_000_000_000.0,
        )
        system = build_tree([star, planet])

        assert system.root is star
        assert star.orbit is None

    def test_root_fallback_unresolved_reference(self) -> None:
        """Body whose referenceBody is not in the index is treated as root."""
        orphan = _make_body(
            "Orphan",
            reference_body_name="NonExistentStar",
            is_home_world=True,
            orbit_sma=10_000_000_000.0,
        )
        system = build_tree([orphan])

        assert system.root is orphan

    def test_bodies_dict_populated(self) -> None:
        """All bodies appear in the CelestialSystem.bodies dict."""
        star = _make_body("Star")
        planet = _make_body(
            "Planet",
            reference_body_name="Star",
            is_home_world=True,
            orbit_sma=10_000_000_000.0,
        )
        moon = _make_body(
            "Moon",
            reference_body_name="Planet",
            orbit_sma=12_000_000.0,
        )
        system = build_tree([star, planet, moon])

        assert "Star" in system.bodies
        assert "Planet" in system.bodies
        assert "Moon" in system.bodies
        assert system.bodies["Star"] is star
        assert system.bodies["Planet"] is planet
        assert system.bodies["Moon"] is moon


# ---------------------------------------------------------------------------
# TestSortByTransferDv
# ---------------------------------------------------------------------------


class TestSortByTransferDv:
    """Tests for sort_by_transfer_dv()."""

    def _build_system(self) -> tuple[CelestialBody, CelestialBody, CelestialBody]:
        """Build a star + two planets system for transfer tests.

        Returns:
            Tuple of (star, inner_planet, outer_planet).
        """
        star = _make_body("Star", radius=261_600_000, gee_asl=1.0)
        inner = _make_body(
            "Inner",
            reference_body_name="Star",
            is_home_world=True,
            orbit_sma=13_599_840_256.0,
        )
        outer = _make_body(
            "Outer",
            reference_body_name="Star",
            orbit_sma=47_000_000_000.0,
        )
        build_tree([star, inner, outer])
        return star, inner, outer

    def test_sorted_by_dv_ascending(self) -> None:
        """Nearer planet has lower Hohmann transfer ΔV than the farther one."""
        star, inner, outer = self._build_system()

        # Add a third planet farther out to have two meaningful targets.
        far = _make_body(
            "Far",
            reference_body_name="Star",
            orbit_sma=120_000_000_000.0,
        )
        far.parent = star
        star.children.append(far)

        results = sort_by_transfer_dv(inner, [outer, far])

        assert len(results) == 2
        bodies_in_order = [b for b, _ in results]
        dvs_in_order = [dv for _, dv in results]

        # outer is closer → lower ΔV → comes first
        assert bodies_in_order[0] is outer
        assert bodies_in_order[1] is far
        # Ascending order
        assert dvs_in_order[0] < dvs_in_order[1]

    def test_returns_positive_dv(self) -> None:
        """All returned ΔV values are strictly positive."""
        _star, inner, outer = self._build_system()

        results = sort_by_transfer_dv(inner, [outer])

        assert len(results) == 1
        _body, dv = results[0]
        assert dv > 0.0

    def test_inner_planet_included(self) -> None:
        """An inner planet (smaller SMA) must appear in sorted results."""
        _star, inner, outer = self._build_system()

        # Sort from outer planet's perspective — inner is the target
        results = sort_by_transfer_dv(outer, [inner])

        assert len(results) == 1
        body, dv = results[0]
        assert body is inner
        assert dv > 0.0


# ---------------------------------------------------------------------------
# TestIsBarycenter
# ---------------------------------------------------------------------------


class TestIsBarycenter:
    """Tests for is_barycenter() heuristic."""

    def test_barycenter_detected(self) -> None:
        """Body with radius < min(children radius) is a barycenter."""
        bary = _make_body("Chaos", radius=10_000.0)
        child1 = _make_body("Farewell", radius=500_000.0, reference_body_name="Chaos")
        child2 = _make_body("Star2", radius=100_000.0, reference_body_name="Chaos")
        bary.children = [child1, child2]
        assert is_barycenter(bary) is True

    def test_normal_planet_not_barycenter(self) -> None:
        """Body with radius > children radius is NOT a barycenter."""
        planet = _make_body("Planet", radius=600_000.0)
        moon = _make_body("Moon", radius=200_000.0, reference_body_name="Planet")
        planet.children = [moon]
        assert is_barycenter(planet) is False

    def test_no_children_not_barycenter(self) -> None:
        """Body with no children is NOT a barycenter."""
        leaf = _make_body("Leaf", radius=100.0)
        leaf.children = []
        assert is_barycenter(leaf) is False

    def test_equal_radius_not_barycenter(self) -> None:
        """Body with radius == child radius is NOT a barycenter (not strictly less)."""
        body = _make_body("Equal", radius=100_000.0)
        child = _make_body("Child", radius=100_000.0, reference_body_name="Equal")
        body.children = [child]
        assert is_barycenter(body) is False
