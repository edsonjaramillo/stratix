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
class EMA:
    window: int
    source: IndicatorSource = "close"
    color: str | None = None
    linewidth: float = 1.5
    label: str = field(default="")
    placement: IndicatorPlacement = "price"
    panel_label: str | None = None
    name: str = field(init=False, default="ema")

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError("EMA window must be greater than zero.")
        if self.linewidth <= 0:
            raise ValueError("EMA linewidth must be greater than zero.")
        if not self.label:
            object.__setattr__(self, "label", f"EMA {self.window}")
        if self.placement == "panel" and self.panel_label is None:
            object.__setattr__(self, "panel_label", self.label)

    def compute(self, bars: Sequence[PreparedBar]) -> list[IndicatorPoint]:
        seed_window: deque[float] = deque()
        seed_sum = 0.0
        multiplier = 2.0 / (self.window + 1)
        ema_value: float | None = None
        points: list[IndicatorPoint] = []

        for bar in bars:
            source_value = bar.value_for(self.source)
            value: float | None = None

            if ema_value is None:
                seed_window.append(source_value)
                seed_sum += source_value

                if len(seed_window) > self.window:
                    seed_sum -= seed_window.popleft()

                if len(seed_window) == self.window:
                    ema_value = seed_sum / self.window
                    value = ema_value
            else:
                ema_value = ((source_value - ema_value) * multiplier) + ema_value
                value = ema_value

            points.append(IndicatorPoint(x=bar.x, timestamp=bar.timestamp, value=value))

        return points

    def draw(self, axis: Axes, bars: Sequence[PreparedBar]) -> bool:
        return draw_line_indicator(self, axis, bars)
