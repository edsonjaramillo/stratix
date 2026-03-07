from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, Literal, cast

import httpx

Timespan = Literal["minute", "hour", "day", "week", "month", "quarter", "year"]
SortOrder = Literal["asc", "desc"]
DateInput = date | datetime | int | str
JSONPrimitive = None | bool | int | float | str
JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
JSONMapping = dict[str, JSONValue]


class StockDataError(Exception):
    pass


class MissingAPIKeyError(StockDataError):
    pass


class InvalidRequestError(StockDataError):
    pass


class APIResponseError(StockDataError):
    pass


@dataclass(slots=True, frozen=True)
class _CacheRequest:
    ticker: str
    multiplier: int
    timespan: Timespan
    start: str | int
    end: str | int
    adjusted: bool
    sort: SortOrder
    limit: int


class _ResponseCache:
    def __init__(self, directory: Path) -> None:
        self._directory: Path = directory

    def load(self, request: _CacheRequest) -> AggregateBarsResponse | None:
        cache_path = self._path_for(request)
        if not cache_path.exists():
            return None

        try:
            payload = cast(object, json.loads(cache_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise APIResponseError("Cached response could not be read.") from exc

        return AggregateBarsResponse.from_api(payload)

    def save(self, request: _CacheRequest, payload: object) -> None:
        if not isinstance(payload, dict):
            raise APIResponseError("API response must be an object.")

        cache_path = self._path_for(request)
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            _ = cache_path.write_text(
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            raise APIResponseError("Cached response could not be written.") from exc

    def _path_for(self, request: _CacheRequest) -> Path:
        serialized_request = json.dumps(
            {
                "ticker": request.ticker,
                "multiplier": request.multiplier,
                "timespan": request.timespan,
                "from": request.start,
                "to": request.end,
                "adjusted": request.adjusted,
                "sort": request.sort,
                "limit": request.limit,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(serialized_request.encode("utf-8")).hexdigest()[:16]
        filename = (
            f"{request.ticker}_{request.multiplier}_{request.timespan}_"
            f"{request.start}_{request.end}_{request.sort}_{request.limit}_"
            f"{'adjusted' if request.adjusted else 'raw'}_{digest}.json"
        )
        safe_filename = "".join(
            character if character.isalnum() or character in {"-", "_", "."} else "_"
            for character in filename
        )
        return self._directory / safe_filename


@dataclass(slots=True, frozen=True)
class AggregateBar:
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: int
    transactions: int | None = None
    volume_weighted_average: float | None = None
    otc: bool | None = None

    @classmethod
    def from_api(cls, payload: object) -> AggregateBar:
        if not isinstance(payload, dict):
            raise APIResponseError("Bar payload must be an object.")
        payload_dict = cast(JSONMapping, payload)

        try:
            open_price = _coerce_float(payload_dict["o"])
            high_price = _coerce_float(payload_dict["h"])
            low_price = _coerce_float(payload_dict["l"])
            close_price = _coerce_float(payload_dict["c"])
            volume = _coerce_float(payload_dict["v"])
            timestamp = _coerce_int(payload_dict["t"])
        except (KeyError, TypeError, ValueError) as exc:
            raise APIResponseError(
                "Bar payload is missing required numeric fields."
            ) from exc

        transactions = _coerce_optional_int(payload_dict.get("n"))
        volume_weighted_average = _coerce_optional_float(payload_dict.get("vw"))
        otc_value = payload_dict.get("otc")
        otc = otc_value if isinstance(otc_value, bool) else None

        return cls(
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            timestamp=timestamp,
            transactions=transactions,
            volume_weighted_average=volume_weighted_average,
            otc=otc,
        )


@dataclass(slots=True, frozen=True)
class AggregateBarsResponse:
    ticker: str
    adjusted: bool | None
    query_count: int | None
    results_count: int | None
    request_id: str | None
    status: str
    next_url: str | None
    results: list[AggregateBar]

    @classmethod
    def from_api(cls, payload: object) -> AggregateBarsResponse:
        if not isinstance(payload, dict):
            raise APIResponseError("API response must be an object.")
        payload_dict = cast(JSONMapping, payload)

        status = payload_dict.get("status")
        ticker = payload_dict.get("ticker")
        if not isinstance(status, str):
            raise APIResponseError("API response is missing a string status.")
        if not isinstance(ticker, str):
            raise APIResponseError("API response is missing a string ticker.")

        raw_results_value = payload_dict.get("results", [])
        raw_results: list[JSONValue] | None
        if raw_results_value is None:
            raw_results = []
        elif isinstance(raw_results_value, list):
            raw_results = raw_results_value
        else:
            raw_results = None
        if not isinstance(raw_results, list):
            raise APIResponseError("API response results must be a list.")

        request_id = payload_dict.get("request_id")
        next_url = payload_dict.get("next_url")
        adjusted = payload_dict.get("adjusted")

        return cls(
            ticker=ticker,
            adjusted=adjusted if isinstance(adjusted, bool) else None,
            query_count=_coerce_optional_int(payload_dict.get("queryCount")),
            results_count=_coerce_optional_int(payload_dict.get("resultsCount")),
            request_id=request_id if isinstance(request_id, str) else None,
            status=status,
            next_url=next_url if isinstance(next_url, str) else None,
            results=[AggregateBar.from_api(item) for item in raw_results],
        )


class StockData:
    _BASE_URL: Final[str] = "https://api.massive.com"
    _CACHE_DIR: Final[Path] = Path("data")

    def __init__(
        self,
        *,
        api_key_env: str = "MASSIVE_API_KEY",
        client: httpx.Client | None = None,
        base_url: str = _BASE_URL,
        timeout: float = 10.0,
    ) -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise MissingAPIKeyError(
                f"Missing API key. Set the {api_key_env} environment variable."
            )

        self._api_key: str = api_key
        self._client: httpx.Client = client or httpx.Client(
            base_url=base_url, timeout=timeout
        )
        self._owns_client: bool = client is None
        self._cache: _ResponseCache = _ResponseCache(self._CACHE_DIR)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> StockData:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_data(
        self,
        ticker: str,
        *,
        multiplier: int,
        timespan: Timespan,
        start: DateInput,
        end: DateInput,
        adjusted: bool = True,
        sort: SortOrder = "asc",
        limit: int = 5_000,
    ) -> AggregateBarsResponse:
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise InvalidRequestError("Ticker must be a non-empty string.")
        if multiplier < 1:
            raise InvalidRequestError("Multiplier must be greater than or equal to 1.")
        if not 1 <= limit <= 50_000:
            raise InvalidRequestError("Limit must be between 1 and 50000.")
        normalized_start = _normalize_date_input(start)
        normalized_end = _normalize_date_input(end)
        cache_request = _CacheRequest(
            ticker=normalized_ticker,
            multiplier=multiplier,
            timespan=timespan,
            start=normalized_start,
            end=normalized_end,
            adjusted=adjusted,
            sort=sort,
            limit=limit,
        )

        cached_response = self._cache.load(cache_request)
        if cached_response is not None:
            return cached_response

        path = (
            f"/v2/aggs/ticker/{normalized_ticker}/range/"
            f"{multiplier}/{timespan}/{normalized_start}/{normalized_end}"
        )

        try:
            response = self._client.get(
                path,
                params={
                    "adjusted": str(adjusted).lower(),
                    "sort": sort,
                    "limit": limit,
                    "apiKey": self._api_key,
                },
            )
        except httpx.RequestError as exc:
            raise APIResponseError(
                "Massive request failed before a response was received."
            ) from exc

        try:
            _ = response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise APIResponseError(
                f"Massive request failed with status {exc.response.status_code}."
            ) from exc

        try:
            payload = cast(object, response.json())
        except ValueError as exc:
            raise APIResponseError("Massive returned invalid JSON.") from exc

        parsed_response = AggregateBarsResponse.from_api(payload)
        self._cache.save(cache_request, payload)
        return parsed_response


def _normalize_date_input(value: DateInput) -> str | int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return int(value.timestamp() * 1000)

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, int):
        return value

    normalized = value.strip()
    if not normalized:
        raise InvalidRequestError("Date input strings must be non-empty.")
    return normalized


def _coerce_int(value: JSONValue) -> int:
    if isinstance(value, bool):
        raise TypeError("Boolean values are not accepted as integers.")

    if isinstance(value, int):
        return value

    if isinstance(value, float | str):
        return int(value)

    raise TypeError("Expected an integer-compatible value.")


def _coerce_optional_int(value: JSONValue) -> int | None:
    if value is None:
        return None

    try:
        return _coerce_int(value)
    except (TypeError, ValueError) as exc:
        raise APIResponseError(
            "Expected an integer-compatible value in the API response."
        ) from exc


def _coerce_float(value: JSONValue) -> float:
    if isinstance(value, bool):
        raise TypeError("Boolean values are not accepted as floats.")

    if isinstance(value, int | float):
        return float(value)

    if isinstance(value, str):
        return float(value)

    raise TypeError("Expected a float-compatible value.")


def _coerce_optional_float(value: JSONValue) -> float | None:
    if value is None:
        return None

    try:
        return _coerce_float(value)
    except (TypeError, ValueError) as exc:
        raise APIResponseError(
            "Expected a float-compatible value in the API response."
        ) from exc
