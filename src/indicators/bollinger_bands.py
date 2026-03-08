from __future__ import annotations

# pyright: reportUnknownMemberType=false

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import sqrt

from matplotlib.axes import Axes

from src.colors import Colors
from src.indicators.base import (
    IndicatorPlacement,
    IndicatorPoint,
    IndicatorSource,
    PreparedBar,
)


@dataclass(slots=True, frozen=True)
class BollingerBands:
    window: int = 20
    stddev_multiplier: float = 2.0
    source: IndicatorSource = "close"
    color: str | None = None
    band_color: str | None = None
    linewidth: float = 1.5
    label: str = field(default="")
    placement: IndicatorPlacement = "price"
    panel_label: str | None = None
    middle_color: str | None = None
    show_fill: bool = True
    fill_color: str | None = None
    fill_alpha: float = 0.12
    name: str = field(init=False, default="bollinger_bands")

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError("Bollinger Bands window must be greater than zero.")
        if self.stddev_multiplier < 0:
            raise ValueError(
                "Bollinger Bands stddev_multiplier must be zero or greater."
            )
        if self.linewidth <= 0:
            raise ValueError("Bollinger Bands linewidth must be greater than zero.")
        if not 0.0 <= self.fill_alpha <= 1.0:
            raise ValueError("Bollinger Bands fill_alpha must be between 0 and 1.")
        if not self.label:
            object.__setattr__(
                self, "label", f"BB {self.window} {self.stddev_multiplier:g}"
            )
        if self.placement == "panel" and self.panel_label is None:
            object.__setattr__(self, "panel_label", self.label)
        if self.band_color is None:
            object.__setattr__(self, "band_color", self.color or Colors.SKY)
        if self.middle_color is None:
            object.__setattr__(self, "middle_color", self.color or Colors.AMBER)
        if self.fill_color is None:
            object.__setattr__(self, "fill_color", self.color or Colors.SKY)

    def compute(self, bars: Sequence[PreparedBar]) -> list[IndicatorPoint]:
        points: list[IndicatorPoint] = []
        for bar, _, middle, _ in self._compute_bands(bars):
            points.append(
                IndicatorPoint(x=bar.x, timestamp=bar.timestamp, value=middle)
            )
        return points

    def draw(self, axis: Axes, bars: Sequence[PreparedBar]) -> bool:
        band_points = self._compute_bands(bars)
        if not band_points:
            return False

        x_values = [bar.x for bar, _, _, _ in band_points]
        upper_values = [upper for _, upper, _, _ in band_points]
        middle_values = [middle for _, _, middle, _ in band_points]
        lower_values = [lower for _, _, _, lower in band_points]

        if self.show_fill and self.fill_color is not None:
            _ = axis.fill_between(
                x_values,
                upper_values,
                lower_values,
                color=self.fill_color,
                alpha=self.fill_alpha,
            )

        _ = axis.plot(
            x_values,
            upper_values,
            label=f"{self.label} Upper",
            linewidth=self.linewidth,
            color=self.band_color,
        )
        _ = axis.plot(
            x_values,
            middle_values,
            label=f"{self.label} Middle",
            linewidth=self.linewidth,
            color=self.middle_color,
        )
        _ = axis.plot(
            x_values,
            lower_values,
            label=f"{self.label} Lower",
            linewidth=self.linewidth,
            color=self.band_color,
        )

        return True

    def tooltip_lines(self, bars: Sequence[PreparedBar]) -> Mapping[float, list[str]]:
        lines: dict[float, list[str]] = {}
        for bar, upper, middle, lower in self._compute_bands(bars):
            lines[bar.x] = [
                f"{self.label} Upper: {upper:.2f}",
                f"{self.label} Middle: {middle:.2f}",
                f"{self.label} Lower: {lower:.2f}",
            ]
        return lines

    def _compute_bands(
        self, bars: Sequence[PreparedBar]
    ) -> list[tuple[PreparedBar, float, float, float]]:
        rolling_window: deque[float] = deque()
        rolling_sum = 0.0
        rolling_sum_squares = 0.0
        band_points: list[tuple[PreparedBar, float, float, float]] = []

        for bar in bars:
            source_value = bar.value_for(self.source)
            rolling_window.append(source_value)
            rolling_sum += source_value
            rolling_sum_squares += source_value * source_value

            if len(rolling_window) > self.window:
                removed_value = rolling_window.popleft()
                rolling_sum -= removed_value
                rolling_sum_squares -= removed_value * removed_value

            if len(rolling_window) != self.window:
                continue

            middle = rolling_sum / self.window
            variance = max((rolling_sum_squares / self.window) - (middle * middle), 0.0)
            stddev = sqrt(variance)
            offset = stddev * self.stddev_multiplier

            band_points.append((bar, middle + offset, middle, middle - offset))

        return band_points
