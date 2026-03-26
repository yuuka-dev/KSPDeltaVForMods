"""Tests for CLI display functions.

CLI表示関数のテスト。
"""

from __future__ import annotations

import json
import os
from io import StringIO
from unittest.mock import patch

from kopdeltav.calculator import DvStep, SegmentType


class TestRouteToJson:
    """Tests for _route_to_json output format."""

    def test_valid_json(self) -> None:
        """Verify JSON output is well-formed with correct structure."""
        from run import _route_to_json

        steps = [
            DvStep(
                label="Launch",
                dv=3108.0,
                cumulative=3108.0,
                segment_type=SegmentType.LAUNCH,
            ),
            DvStep(
                label="Escape",
                dv=1053.0,
                cumulative=4161.0,
                segment_type=SegmentType.ESCAPE,
            ),
        ]
        result = _route_to_json(steps, "Kerbin", "Target")
        data = json.loads(result)
        assert data["route"]["from"] == "Kerbin"
        assert data["route"]["to"] == "Target"
        assert len(data["route"]["segments"]) == 2
        assert data["route"]["total_dv"] == 4161.0

    def test_empty_route(self) -> None:
        """Verify empty route produces valid JSON with zero total."""
        from run import _route_to_json

        result = _route_to_json([], "A", "B")
        data = json.loads(result)
        assert data["route"]["total_dv"] == 0.0
        assert data["route"]["segments"] == []

    def test_segment_fields(self) -> None:
        """Verify each segment has required fields."""
        from run import _route_to_json

        steps = [
            DvStep(
                label="Launch to low orbit",
                dv=3108.0,
                cumulative=3108.0,
                segment_type=SegmentType.LAUNCH,
                note="test note",
            ),
        ]
        result = _route_to_json(steps, "Kerbin", "Mun")
        data = json.loads(result)
        seg = data["route"]["segments"][0]
        assert seg["label"] == "Launch to low orbit"
        assert seg["type"] == "launch"
        assert seg["note"] == "test note"
        assert "dv" in seg
        assert "cumulative" in seg


class TestRouteToMarkdown:
    """Tests for _route_to_markdown output format."""

    def test_valid_markdown(self) -> None:
        """Verify Markdown output contains expected table rows."""
        from run import _route_to_markdown

        steps = [
            DvStep(
                label="Launch",
                dv=3108.0,
                cumulative=3108.0,
                segment_type=SegmentType.LAUNCH,
            ),
            DvStep(
                label="Escape",
                dv=1053.0,
                cumulative=4161.0,
                segment_type=SegmentType.ESCAPE,
            ),
        ]
        result = _route_to_markdown(steps, "Kerbin", "Target", "en")
        assert "| 1 |" in result
        assert "| 2 |" in result
        assert "4,161" in result

    def test_markdown_header(self) -> None:
        """Verify Markdown header contains route info."""
        from run import _route_to_markdown

        steps = [
            DvStep(
                label="Launch",
                dv=100.0,
                cumulative=100.0,
                segment_type=SegmentType.LAUNCH,
            ),
        ]
        result = _route_to_markdown(steps, "Kerbin", "Duna", "en")
        assert "Kerbin" in result
        assert "Duna" in result
        assert "##" in result

    def test_empty_markdown(self) -> None:
        """Verify empty steps produce a table with no data rows."""
        from run import _route_to_markdown

        result = _route_to_markdown([], "A", "B", "en")
        assert "| # |" in result
        assert "| 1 |" not in result


class TestSubwayMapSnapshot:
    """Tests for _print_subway_route visual output."""

    def test_no_ansi_in_no_color_mode(self) -> None:
        """Verify no ANSI escape codes appear when color is disabled."""
        import sys

        from run import _print_subway_route

        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            steps = [
                DvStep(
                    label="Launch to low orbit",
                    dv=3108.0,
                    cumulative=3108.0,
                    segment_type=SegmentType.LAUNCH,
                ),
            ]
            _print_subway_route(
                steps,
                "Kerbin",
                "Target",
                "en",
                use_color=False,
                use_unicode=True,
            )
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        assert "\033[" not in output
        assert "3,108" in output

    def test_ascii_fallback(self) -> None:
        """Verify Unicode symbols are not used when unicode is disabled."""
        import sys

        from run import _print_subway_route

        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            steps = [
                DvStep(
                    label="Launch to low orbit",
                    dv=3108.0,
                    cumulative=3108.0,
                    segment_type=SegmentType.LAUNCH,
                ),
            ]
            _print_subway_route(
                steps,
                "Kerbin",
                "Target",
                "en",
                use_color=False,
                use_unicode=False,
            )
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        assert "\u25cf" not in output  # ●
        assert "\u2502" not in output  # │

    def test_multi_step_route(self) -> None:
        """Verify multi-step route has correct node structure."""
        import sys

        from run import _print_subway_route

        buf = StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            steps = [
                DvStep(
                    label="Launch to low orbit",
                    dv=3108.0,
                    cumulative=3108.0,
                    segment_type=SegmentType.LAUNCH,
                ),
                DvStep(
                    label="Escape Kerbin",
                    dv=1053.0,
                    cumulative=4161.0,
                    segment_type=SegmentType.ESCAPE,
                ),
                DvStep(
                    label="Transfer",
                    dv=459.0,
                    cumulative=4620.0,
                    segment_type=SegmentType.TRANSFER,
                ),
                DvStep(
                    label="Capture",
                    dv=298.0,
                    cumulative=4918.0,
                    segment_type=SegmentType.CAPTURE,
                ),
                DvStep(
                    label="Landing",
                    dv=719.0,
                    cumulative=5637.0,
                    segment_type=SegmentType.LANDING,
                ),
            ]
            _print_subway_route(
                steps,
                "Kerbin",
                "Magnifica",
                "en",
                use_color=False,
                use_unicode=True,
            )
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        assert "Kerbin" in output
        assert "Magnifica" in output
        assert "5,637" in output
        # Should have "Low orbit" and "SOI edge" intermediate nodes
        assert "Low orbit" in output
        assert "SOI edge" in output


class TestTerminalDetection:
    """Tests for terminal capability detection functions."""

    def test_no_color_env(self) -> None:
        """Verify NO_COLOR env var disables color."""
        from run import _supports_color

        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert _supports_color() is False

    def test_dumb_terminal(self) -> None:
        """Verify TERM=dumb disables color."""
        from run import _supports_color

        with patch.dict(os.environ, {"TERM": "dumb"}, clear=False):
            assert _supports_color() is False

    def test_non_tty_no_color(self) -> None:
        """Verify non-TTY stdout disables color."""
        from run import _supports_color

        with patch("sys.stdout", new=StringIO()):
            assert _supports_color() is False

    def test_supports_unicode_utf8(self) -> None:
        """Verify UTF-8 encoding is detected as unicode-capable."""
        from unittest.mock import MagicMock

        from run import _supports_unicode

        mock_stdout = MagicMock()
        mock_stdout.encoding = "utf-8"
        with patch("sys.stdout", mock_stdout):
            assert _supports_unicode() is True

    def test_supports_unicode_ascii(self) -> None:
        """Verify ASCII encoding is detected as not unicode-capable."""
        from unittest.mock import MagicMock

        from run import _supports_unicode

        mock_stdout = MagicMock()
        mock_stdout.encoding = "ascii"
        with patch("sys.stdout", mock_stdout):
            assert _supports_unicode() is False


class TestColorFunction:
    """Tests for the _color utility function."""

    def test_color_enabled(self) -> None:
        """Verify ANSI codes are added when color is enabled."""
        from run import _color

        result = _color("test", "green", use_color=True)
        assert "\033[32m" in result
        assert "\033[0m" in result
        assert "test" in result

    def test_color_disabled(self) -> None:
        """Verify no ANSI codes when color is disabled."""
        from run import _color

        result = _color("test", "green", use_color=False)
        assert result == "test"
        assert "\033[" not in result

    def test_unknown_color(self) -> None:
        """Verify unknown color names return plain text."""
        from run import _color

        result = _color("test", "nonexistent", use_color=True)
        assert result == "test"


class TestFormatTransferTime:
    """Tests for _format_transfer_time helper."""

    def test_days_and_hours(self) -> None:
        """Verify formatting for multi-day durations."""
        from run import _format_transfer_time

        # 2 days 3 hours = 2*86400 + 3*3600 = 183600
        result = _format_transfer_time(183600.0)
        assert result == "2d 3h"

    def test_hours_and_minutes(self) -> None:
        """Verify formatting for sub-day durations."""
        from run import _format_transfer_time

        # 5 hours 30 minutes = 5*3600 + 30*60 = 19800
        result = _format_transfer_time(19800.0)
        assert result == "5h 30m"

    def test_minutes_only(self) -> None:
        """Verify formatting for sub-hour durations."""
        from run import _format_transfer_time

        # 45 minutes = 2700
        result = _format_transfer_time(2700.0)
        assert result == "45m"
