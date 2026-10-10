"""Settings for `just search`, loaded from config/search.toml."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue, PositiveInt


class HttpConfig(BaseModel):
    """How every request identifies itself and how long it may take."""

    model_config = ConfigDict(extra="forbid")

    user_agent: str
    timeout_seconds: float


class AlgoliaConfig(BaseModel):
    """The Algolia index behind hn.algolia.com and the search parameters the website sends."""

    model_config = ConfigDict(extra="forbid")

    application_id: str
    api_key: str
    index: str
    params: dict[str, JsonValue]


class DiscussionsConfig(BaseModel):
    """Where the official Hacker News API serves each item; `{id}` is replaced by the item ID.

    A discussion is a story with all its comments, one request per item, at most
    max_concurrent_requests at a time.
    """

    model_config = ConfigDict(extra="forbid")

    item_url: str
    max_concurrent_requests: PositiveInt


class OutputConfig(BaseModel):
    """Where saved searches go."""

    model_config = ConfigDict(extra="forbid")

    directory: Path


class SearchConfig(BaseModel):
    """All settings for `just search`."""

    model_config = ConfigDict(extra="forbid")

    http: HttpConfig
    algolia: AlgoliaConfig
    discussions: DiscussionsConfig
    output: OutputConfig


def load_config(path: Path) -> SearchConfig:
    """Load the settings from a TOML file, rejecting missing and unknown settings."""
    with path.open("rb") as file:
        return SearchConfig.model_validate(tomllib.load(file))
