from __future__ import annotations

# pyright: reportUnknownMemberType=false

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from matplotlib.axes import Axes

IndicatorPlacement = Literal["price", "panel"]
IndicatorSource = Literal["open", "high", "low", "close", "volume"]


@dataclass(slots=True, frozen=True)
class PreparedBar:
    x: float
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def value_for(self, source: IndicatorSource) -> float:
        return {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }[source]


@dataclass(slots=True, frozen=True)
class IndicatorPoint:
    x: float
    timestamp: datetime
    value: float | None


@dataclass(slots=True, frozen=True)
class RenderedIndicatorPoint:
    x: float
    timestamp: datetime
    value: float


class Indicator(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def placement(self) -> IndicatorPlacement: ...

    @property
    def panel_label(self) -> str | None: ...

    @property
    def label(self) -> str: ...

    @property
    def color(self) -> str | None: ...

    @property
    def linewidth(self) -> float: ...

    def compute(self, bars: Sequence[PreparedBar]) -> Sequence[IndicatorPoint]: ...

    def draw(self, axis: Axes, bars: Sequence[PreparedBar]) -> bool: ...


def collect_rendered_points(
    indicator: Indicator, bars: Sequence[PreparedBar]
) -> list[RenderedIndicatorPoint]:
    rendered_points: list[RenderedIndicatorPoint] = []

    for point in indicator.compute(bars):
        if point.value is None:
            continue
        rendered_points.append(
            RenderedIndicatorPoint(
                x=point.x,
                timestamp=point.timestamp,
                value=point.value,
            )
        )

    return rendered_points


def draw_line_indicator(
    indicator: Indicator, axis: Axes, bars: Sequence[PreparedBar]
) -> bool:
    rendered_points = collect_rendered_points(indicator, bars)
    x_values = [point.x for point in rendered_points]
    y_values = [point.value for point in rendered_points]

    if not x_values:
        return False

    if indicator.color is not None:
        _ = axis.plot(
            x_values,
            y_values,
            label=indicator.label,
            linewidth=indicator.linewidth,
            color=indicator.color,
        )
    else:
        _ = axis.plot(
            x_values,
            y_values,
            label=indicator.label,
            linewidth=indicator.linewidth,
        )
    return True
