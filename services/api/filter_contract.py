"""Shared parameterized filter compiler for OpenData query surfaces."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal, Protocol

from fastapi import HTTPException


class FilterLike(Protocol):
    column: str
    operator: Literal["equals", "not_equals", "greater_than", "greater_or_equal", "less_than", "less_or_equal", "in", "date_range"]
    value: str
    values: list[str]


class ColumnLike(Protocol):
    @property
    def kind(self) -> str: ...


SqlParameter = str | float
QuoteIdentifier = Callable[[str, list[str]], str]
IsDate = Callable[[str], bool]
IsNumber = Callable[[str], bool]


def compile_filters(
    filters: Sequence[FilterLike],
    headers: list[str],
    profile_columns: Mapping[str, ColumnLike],
    allowed_columns: set[str],
    *,
    quote_identifier: QuoteIdentifier,
    is_date: IsDate,
    is_number: IsNumber,
) -> tuple[list[str], list[SqlParameter]]:
    """Compile only validated, parameterized predicates for non-sensitive fields."""
    clauses: list[str] = []
    parameters: list[SqlParameter] = []
    operators = {"equals": "=", "not_equals": "<>", "greater_than": ">", "greater_or_equal": ">=", "less_than": "<", "less_or_equal": "<="}
    for item in filters:
        if item.column not in allowed_columns:
            raise HTTPException(422, "Only non-sensitive, non-identifier columns can be used in filters.")
        field = quote_identifier(item.column, headers)
        kind = profile_columns[item.column].kind
        if item.operator == "in":
            if kind not in {"cat", "time", "num"}:
                raise HTTPException(422, "IN filters require a categorical, time, or numeric field.")
            clauses.append(f"{field} IN ({', '.join('?' for _ in item.values)})")
            parameters.extend(item.values)
        elif item.operator == "date_range":
            if kind != "time" or len(item.values) != 2 or not all(is_date(value) for value in item.values):
                raise HTTPException(422, f"date_range requires two valid dates for time field {item.column}.")
            clauses.append(f"TRY_CAST({field} AS TIMESTAMP) BETWEEN TRY_CAST(? AS TIMESTAMP) AND TRY_CAST(? AS TIMESTAMP)")
            parameters.extend(item.values)
        elif item.operator in operators:
            operator = operators[item.operator]
            if item.operator in {"greater_than", "greater_or_equal", "less_than", "less_or_equal"}:
                if kind != "num" or not is_number(item.value):
                    raise HTTPException(422, f"Numeric comparison requires a numeric value for {item.column}.")
                clauses.append(f"TRY_CAST(REPLACE({field}, ',', '') AS DOUBLE) {operator} ?")
                parameters.append(float(item.value.replace(',', '')))
            else:
                clauses.append(f"{field} {operator} ?")
                parameters.append(item.value)
    return clauses, parameters
