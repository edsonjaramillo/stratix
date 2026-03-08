from src.chart import Chart
from src.colors import Colors
from src.indicators import EMA
from src.stock_data import StockData, Timespan

ticker = "AAPL"
timespan: Timespan = "day"
start = "2025-01-01"
end = "2025-12-31"


def main() -> None:
    with StockData() as stock_data:
        data = stock_data.get_data(
            ticker=ticker,
            multiplier=1,
            timespan=timespan,
            start=start,
            end=end,
        )

    Chart(
        data,
        show_volume=True,
        indicators=[
            EMA(window=9, color=Colors.CYAN),
            EMA(window=21, color=Colors.YELLOW),
            EMA(window=50, color=Colors.ORANGE),
            EMA(window=200, color=Colors.RED),
        ],
    ).show()


if __name__ == "__main__":
    main()
