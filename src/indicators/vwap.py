from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from matplotlib.axes import Axes

from src.indicators.base import (
    IndicatorPlacement,
    IndicatorPoint,
    PreparedBar,
    draw_line_indicator,
)


@dataclass(slots=True, frozen=True)
class VWAP:
    color: str | None = None
    linewidth: float = 1.5
    label: str = field(default="")
    placement: IndicatorPlacement = "price"
    panel_label: str | None = None
    name: str = field(init=False, default="vwap")

    def __post_init__(self) -> None:
        if self.linewidth <= 0:
            raise ValueError("VWAP linewidth must be greater than zero.")
        if not self.label:
            object.__setattr__(self, "label", "VWAP")
        if self.placement == "panel" and self.panel_label is None:
            object.__setattr__(self, "panel_label", self.label)

    def compute(self, bars: Sequence[PreparedBar]) -> list[IndicatorPoint]:
        cumulative_price_volume = 0.0
        cumulative_volume = 0.0
        points: list[IndicatorPoint] = []

        for bar in bars:
            typical_price = (bar.high + bar.low + bar.close) / 3.0
            cumulative_price_volume += typical_price * bar.volume
            cumulative_volume += bar.volume

            value = (
                cumulative_price_volume / cumulative_volume
                if cumulative_volume > 0
                else None
            )
            points.append(IndicatorPoint(x=bar.x, timestamp=bar.timestamp, value=value))

        return points

    def draw(self, axis: Axes, bars: Sequence[PreparedBar]) -> bool:
        return draw_line_indicator(self, axis, bars)
