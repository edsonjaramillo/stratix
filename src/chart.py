from __future__ import annotations

# pyright: reportAny=false, reportUnknownMemberType=false, reportUnusedCallResult=false

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, final

import matplotlib.dates as mdates
from matplotlib import pyplot as plt
from matplotlib.backend_bases import Event, MouseEvent
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.text import Annotation

from src.colors import Colors
from src.indicators import Indicator, PreparedBar
from src.indicators.base import collect_rendered_points
from src.stock_data import AggregateBar, AggregateBarsResponse


class ChartError(Exception):
    pass


@dataclass(slots=True, frozen=True)
class _HoverTarget:
    artist: Rectangle
    tooltip_kind: str
    anchor_y: float
    axis: Axes
    bar: PreparedBar


@final
class Chart:
    def __init__(
        self,
        data: AggregateBarsResponse,
        *,
        show_volume: bool = False,
        figsize: tuple[float, float] = (12.0, 7.0),
        indicators: Sequence[Indicator] = (),
    ) -> None:
        self._data: AggregateBarsResponse = data
        self._show_volume: bool = show_volume
        self._figsize: tuple[float, float] = figsize
        self._indicators: tuple[Indicator, ...] = tuple(indicators)
        self._prepared_bars: list[PreparedBar] = []
        self._hover_targets: list[_HoverTarget] = []
        self._hover_annotations: dict[Axes, Annotation] = {}
        self._price_tooltip_indicator_values: dict[float, list[str]] = {}

    def build_figure(self) -> tuple[Figure, tuple[Axes, Axes | None]]:
        bars = self._prepare_bars()
        panel_indicators = [
            indicator
            for indicator in self._indicators
            if indicator.placement == "panel"
        ]

        self._prepared_bars = bars
        self._hover_targets = []
        self._hover_annotations = {}
        self._price_tooltip_indicator_values = {}

        figure, price_ax, volume_ax, panel_axes = self._create_axes(
            panel_count=len(panel_indicators)
        )

        candle_width = self._candle_width(bars)
        self._hover_annotations[price_ax] = self._create_hover_annotation(price_ax)

        self._draw_price_panel(price_ax, bars, candle_width)
        if volume_ax is not None:
            self._draw_volume_panel(volume_ax, bars, candle_width)
            self._hover_annotations[volume_ax] = self._create_hover_annotation(
                volume_ax
            )
        self._draw_indicators(price_ax, panel_axes, bars)

        price_ax.set_title(self._build_title())
        price_ax.set_ylabel("Price")
        price_ax.grid(True, axis="y", alpha=0.2)

        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        if volume_ax is not None:
            target_axis = volume_ax
        elif panel_axes:
            target_axis = panel_axes[-1]
        else:
            target_axis = price_ax
        target_axis.xaxis.set_major_locator(locator)
        target_axis.xaxis.set_major_formatter(formatter)

        figure.autofmt_xdate()
        figure.tight_layout()

        return figure, (price_ax, volume_ax)

    def show(self) -> None:
        figure, _ = self.build_figure()
        self._connect_hover(figure)
        try:
            plt.show()
        finally:
            plt.close(figure)

    def save(self, path: str | Path) -> Path:
        output_path = Path(path)
        figure, _ = self.build_figure()
        try:
            figure.savefig(output_path, bbox_inches="tight")
        finally:
            plt.close(figure)
        return output_path

    def _prepare_bars(self) -> list[PreparedBar]:
        if not self._data.results:
            raise ChartError("AggregateBarsResponse results are empty.")

        sorted_bars = sorted(self._data.results, key=lambda bar: bar.timestamp)
        return [self._prepare_bar(bar) for bar in sorted_bars]

    def _prepare_bar(self, bar: AggregateBar) -> PreparedBar:
        timestamp = datetime.fromtimestamp(bar.timestamp / 1000, tz=UTC)
        return PreparedBar(
            x=cast(float, mdates.date2num(timestamp)),
            timestamp=timestamp,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )

    def _build_title(self) -> str:
        adjustment_label = "Adjusted" if self._data.adjusted else "Raw"
        return f"{self._data.ticker} Price Chart ({adjustment_label})"

    def _create_axes(
        self, *, panel_count: int
    ) -> tuple[Figure, Axes, Axes | None, list[Axes]]:
        row_count = 1 + panel_count + int(self._show_volume)
        if row_count == 1:
            figure, axis = plt.subplots(figsize=self._figsize)
            return figure, axis, None, []

        height_ratios: list[float] = [4.0]
        height_ratios.extend([1.5] * panel_count)
        if self._show_volume:
            height_ratios.append(1.0)

        figure, raw_axes = plt.subplots(
            row_count,
            1,
            figsize=self._figsize,
            sharex=True,
            gridspec_kw={"height_ratios": height_ratios, "hspace": 0.0},
        )
        axes = list(cast(Sequence[Axes], raw_axes))
        price_ax = axes[0]
        panel_axes = axes[1 : 1 + panel_count]
        volume_ax = axes[-1] if self._show_volume else None
        return figure, price_ax, volume_ax, panel_axes

    def _candle_width(self, bars: list[PreparedBar]) -> float:
        if len(bars) < 2:
            return 0.6

        min_spacing = min(
            current.x - previous.x
            for previous, current in zip(bars, bars[1:], strict=False)
        )
        if min_spacing <= 0:
            return 0.6
        return min_spacing * 0.6

    def _draw_price_panel(
        self, axis: Axes, bars: list[PreparedBar], candle_width: float
    ) -> None:
        for bar in bars:
            up_day = bar.close >= bar.open
            color = Colors.GREEN if up_day else Colors.RED

            axis.vlines(bar.x, bar.low, bar.high, color=color, linewidth=1.0)

            body_bottom = min(bar.open, bar.close)
            body_height = abs(bar.close - bar.open)
            if body_height == 0:
                axis.hlines(
                    bar.open,
                    bar.x - candle_width / 2,
                    bar.x + candle_width / 2,
                    color=color,
                    linewidth=1.5,
                )
                hover_rect = Rectangle(
                    (bar.x - candle_width / 2, bar.open - 0.01),
                    candle_width,
                    0.02,
                    facecolor="none",
                    edgecolor="none",
                )
                axis.add_patch(hover_rect)
                self._hover_targets.append(
                    _HoverTarget(
                        artist=hover_rect,
                        bar=bar,
                        tooltip_kind="price",
                        anchor_y=bar.open,
                        axis=axis,
                    )
                )
                continue

            candle = Rectangle(
                (bar.x - candle_width / 2, body_bottom),
                candle_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=1.0,
            )
            axis.add_patch(candle)
            self._hover_targets.append(
                _HoverTarget(
                    artist=candle,
                    bar=bar,
                    tooltip_kind="price",
                    anchor_y=max(bar.open, bar.close),
                    axis=axis,
                )
            )

        axis.set_xlim(bars[0].x - candle_width, bars[-1].x + candle_width)

    def _draw_volume_panel(
        self, axis: Axes, bars: list[PreparedBar], candle_width: float
    ) -> None:
        colors = [Colors.GREEN if bar.close >= bar.open else Colors.RED for bar in bars]
        volume_bars = axis.bar(
            [bar.x for bar in bars],
            [bar.volume for bar in bars],
            width=candle_width,
            color=colors,
            alpha=0.55,
            align="center",
        )
        for rectangle, bar in zip(volume_bars.patches, bars, strict=False):
            self._hover_targets.append(
                _HoverTarget(
                    artist=rectangle,
                    bar=bar,
                    tooltip_kind="volume",
                    anchor_y=rectangle.get_height(),
                    axis=axis,
                )
            )
        axis.set_ylabel("Volume")
        axis.grid(True, axis="y", alpha=0.2)

    def _draw_indicators(
        self,
        price_ax: Axes,
        panel_axes: Sequence[Axes],
        bars: Sequence[PreparedBar],
    ) -> None:
        panel_axis_index = 0
        has_overlay_indicator = False

        for indicator in self._indicators:
            if indicator.placement == "panel":
                if panel_axis_index >= len(panel_axes):
                    raise ChartError("Indicator axis allocation is out of sync.")
                axis = panel_axes[panel_axis_index]
                panel_axis_index += 1
                axis.set_ylabel(indicator.panel_label or indicator.label)
                axis.grid(True, axis="y", alpha=0.2)
            else:
                axis = price_ax

            rendered = indicator.draw(axis, bars)
            if rendered and indicator.placement == "price":
                self._cache_price_tooltip_indicator_values(indicator, bars)
            if rendered and indicator.placement == "price":
                has_overlay_indicator = True

        if has_overlay_indicator:
            price_ax.legend(loc="upper left")

    def _cache_price_tooltip_indicator_values(
        self, indicator: Indicator, bars: Sequence[PreparedBar]
    ) -> None:
        rendered_points = collect_rendered_points(indicator, bars)
        if not rendered_points:
            return

        for point in rendered_points:
            labels = self._price_tooltip_indicator_values.setdefault(point.x, [])
            labels.append(f"{indicator.label}: {point.value:.2f}")

    def _connect_hover(self, figure: Figure) -> None:
        if not self._hover_annotations or not self._hover_targets:
            return

        def handle_motion(event: Event) -> None:
            if not isinstance(event, MouseEvent):
                return
            self._on_hover(event, figure)

        _ = figure.canvas.mpl_connect("motion_notify_event", handle_motion)

    def _on_hover(self, event: MouseEvent, figure: Figure) -> None:
        hovered_target = self._find_hover_target(event)
        if hovered_target is None:
            self._hide_hover_annotation(figure)
            return

        if event.inaxes is not hovered_target.axis:
            self._hide_hover_annotation(figure)
            return

        annotation = self._hover_annotations.get(hovered_target.axis)
        if annotation is None:
            return

        for axis, axis_annotation in self._hover_annotations.items():
            axis_annotation.set_visible(axis is hovered_target.axis)

        annotation.xy = (hovered_target.bar.x, hovered_target.anchor_y)
        annotation.set_text(self._build_tooltip(hovered_target))
        annotation.set_visible(True)
        figure.canvas.draw_idle()

    def _find_hover_target(self, event: MouseEvent) -> _HoverTarget | None:
        for target in reversed(self._hover_targets):
            if event.inaxes is not target.axis:
                continue
            contains, _ = target.artist.contains(event)
            if contains:
                return target
        return None

    def _create_hover_annotation(self, axis: Axes) -> Annotation:
        annotation = axis.annotate(
            "",
            xy=(0.0, 0.0),
            xytext=(12.0, 12.0),
            textcoords="offset points",
            ha="left",
            va="bottom",
            bbox={
                "boxstyle": "round,pad=0.4",
                "fc": Colors.WHITE,
                "ec": Colors.RED,
                "alpha": 0.95,
            },
            arrowprops={"arrowstyle": "->", "color": Colors.GRAY, "lw": 0.8},
        )
        annotation.set_visible(False)
        return annotation

    def _hide_hover_annotation(self, figure: Figure) -> None:
        had_visible_annotation = False
        for annotation in self._hover_annotations.values():
            if annotation.get_visible():
                had_visible_annotation = True
                annotation.set_visible(False)

        if not had_visible_annotation:
            return

        figure.canvas.draw_idle()

    def _build_tooltip(self, target: _HoverTarget) -> str:
        if target.tooltip_kind == "price":
            return self._build_price_tooltip(target.bar)
        return self._build_volume_tooltip(target.bar)

    def _build_price_tooltip(self, bar: PreparedBar) -> str:
        date_label = bar.timestamp.astimezone(UTC).strftime("%b %d, %Y")
        change = bar.close - bar.open
        change_percent = 0.0 if bar.open == 0 else (change / bar.open) * 100
        change_label = f"{change:+.2f} ({change_percent:+.2f}%)"
        tooltip = (
            f"{date_label}\n"
            f"Open: {bar.open:.2f}\n"
            f"High: {bar.high:.2f}\n"
            f"Low: {bar.low:.2f}\n"
            f"Close: {bar.close:.2f}\n"
            f"Change: {change_label}"
        )
        indicator_lines = self._price_tooltip_indicator_values.get(bar.x, [])
        if indicator_lines:
            tooltip = "\n".join([tooltip, *indicator_lines])
        return tooltip

    def _build_volume_tooltip(self, bar: PreparedBar) -> str:
        date_label = bar.timestamp.astimezone(UTC).strftime("%b %d, %Y")
        short_volume = self._format_volume(bar.volume)
        raw_volume = f"{int(round(bar.volume)):,}"
        return f"{date_label}\nVolume: {short_volume} shares\nExact: {raw_volume}"

    def _format_volume(self, volume: float) -> str:
        thresholds = (
            (1_000_000_000.0, "B"),
            (1_000_000.0, "M"),
            (1_000.0, "K"),
        )
        absolute_volume = abs(volume)
        for threshold, suffix in thresholds:
            if absolute_volume >= threshold:
                scaled = volume / threshold
                return f"{scaled:.1f}{suffix}"
        return f"{int(round(volume)):,}"
