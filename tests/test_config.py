"""Tests for loading the search settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from search_hackernews.config import load_config

_SETTINGS = """
[http]
user_agent = "test-agent"
timeout_seconds = 30

[algolia]
application_id = "TESTAPP"
api_key = "test-key"
index = "Item_dev"

[algolia.params]
hitsPerPage = 1000

[discussions]
item_url = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
max_concurrent_requests = 8

[output]
directory = "data/output"
"""


def test_load_config_reads_the_settings(tmp_path: Path) -> None:
    path = tmp_path / "search.toml"
    path.write_text(_SETTINGS, encoding="utf-8")

    config = load_config(path)

    assert config.http.user_agent == "test-agent"
    assert config.algolia.params == {"hitsPerPage": 1000}
    assert config.discussions.item_url == "https://hacker-news.firebaseio.com/v0/item/{id}.json"
    assert config.discussions.max_concurrent_requests == 8
    assert config.output.directory == Path("data/output")


@pytest.mark.parametrize(
    "settings",
    [
        _SETTINGS.replace('api_key = "test-key"\n', ""),
        _SETTINGS.replace("[output]\n", '[output]\nformat = "csv"\n'),
    ],
    ids=["missing", "unknown"],
)
def test_load_config_rejects_missing_and_unknown_settings(tmp_path: Path, settings: str) -> None:
    path = tmp_path / "search.toml"
    path.write_text(settings, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)
