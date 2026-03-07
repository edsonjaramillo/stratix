from src.stock_data import StockData

ticker = "AAPL"
timespan = "day"
start = "2025-01-01"
end = "2025-12-31"


def main():
    _ = StockData().get_data(
        ticker="AAPL",
        multiplier=1,
        timespan="day",
        start="2025-01-01",
        end="2025-12-31",
    )


if __name__ == "__main__":
    main()
