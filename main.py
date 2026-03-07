from src.chart import Chart
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

    Chart(data, show_volume=True).show()


if __name__ == "__main__":
    main()
