from src.stock_data import StockData


def main():
    _ = StockData().get_data(
        ticker="AAPL",
        multiplier=1,
        timespan="day",
        from_="2025-01-01",
        to="2025-12-31",
    )


if __name__ == "__main__":
    main()
