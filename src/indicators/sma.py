from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from matplotlib.axes import Axes

from src.indicators.base import (
    IndicatorPlacement,
    IndicatorPoint,
    IndicatorSource,
    PreparedBar,
    draw_line_indicator,
)


@dataclass(slots=True, frozen=True)
class SMA:
    window: int
    source: IndicatorSource = "close"
    color: str | None = None
    linewidth: float = 1.5
    label: str = field(default="")
    placement: IndicatorPlacement = "price"
    panel_label: str | None = None
    name: str = field(init=False, default="sma")

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError("SMA window must be greater than zero.")
        if self.linewidth <= 0:
            raise ValueError("SMA linewidth must be greater than zero.")
        if not self.label:
            object.__setattr__(self, "label", f"SMA {self.window}")
        if self.placement == "panel" and self.panel_label is None:
            object.__setattr__(self, "panel_label", self.label)

    def compute(self, bars: Sequence[PreparedBar]) -> list[IndicatorPoint]:
        rolling_window: deque[float] = deque()
        rolling_sum = 0.0
        points: list[IndicatorPoint] = []

        for bar in bars:
            source_value = bar.value_for(self.source)
            rolling_window.append(source_value)
            rolling_sum += source_value

            if len(rolling_window) > self.window:
                rolling_sum -= rolling_window.popleft()

            average: float | None = None
            if len(rolling_window) == self.window:
                average = rolling_sum / self.window

            points.append(
                IndicatorPoint(x=bar.x, timestamp=bar.timestamp, value=average)
            )

        return points

    def draw(self, axis: Axes, bars: Sequence[PreparedBar]) -> bool:
        return draw_line_indicator(self, axis, bars)
