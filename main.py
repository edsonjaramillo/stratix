from src.chart import Chart
from src.indicators import SMA
from src.stock_data import StockData, Timespan
from src.colors import Colors

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
            SMA(window=20, color=Colors.CYAN),
            SMA(window=50, color=Colors.YELLOW),
            SMA(window=100, color=Colors.ORANGE),
            SMA(window=200, color=Colors.RED),
        ],
    ).show()


if __name__ == "__main__":
    main()
