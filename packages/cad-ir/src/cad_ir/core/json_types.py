"""The JSON value type used across the shared core."""

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
