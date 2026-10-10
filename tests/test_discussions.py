"""Tests for downloading a story's comment tree from the official Hacker News API."""

import json
import threading
import time
from typing import Any

import httpx
import pytest

from search_hackernews.config import DiscussionsConfig
from search_hackernews.discussions import fetch_discussion
from tests.helpers import item_response, recorded_items

_CONFIG = DiscussionsConfig(item_url="https://hacker-news.firebaseio.com/v0/item/{id}.json", max_concurrent_requests=4)
_STORY = "47542553"


def _client(items: dict[str, dict[str, Any]], requested: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return item_response(items, request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _ids(node: dict[str, Any]) -> tuple[int, list[Any]]:
    """The item IDs of a discussion, nested like its comments."""
    return node["id"], [_ids(comment) for comment in node["comments"]]


def test_fetch_discussion_nests_each_comment_under_its_parent_in_the_api_order() -> None:
    with _client(recorded_items(), []) as client:
        discussion = json.loads(fetch_discussion(client, _CONFIG, _STORY))

    assert _ids(discussion) == (
        47542553,
        [
            (47546447, [(47548311, [])]),
            (47543168, [(47545725, [])]),
            (47542672, [(47545712, [(47617904, [])])]),
        ],
    )


def test_fetch_discussion_keeps_every_field_the_api_serves() -> None:
    items = recorded_items()

    with _client(items, []) as client:
        discussion = json.loads(fetch_discussion(client, _CONFIG, _STORY))

    reply = discussion["comments"][2]["comments"][0]
    assert {key: value for key, value in discussion.items() if key != "comments"} == items["47542553"]
    assert {key: value for key, value in reply.items() if key != "comments"} == items["47545712"]


def test_fetch_discussion_requests_the_story_and_each_comment_once() -> None:
    requested: list[str] = []

    with _client(recorded_items(), requested) as client:
        fetch_discussion(client, _CONFIG, _STORY)

    assert sorted(requested) == sorted(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json" for item_id in recorded_items())


def test_fetch_discussion_keeps_at_most_max_concurrent_requests_in_flight() -> None:
    items = recorded_items()
    lock = threading.Lock()
    in_flight: list[int] = []
    most_in_flight: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            in_flight.append(1)
            most_in_flight.append(len(in_flight))
        time.sleep(0.02)
        with lock:
            in_flight.pop()
        return item_response(items, request)

    config = DiscussionsConfig(item_url=_CONFIG.item_url, max_concurrent_requests=2)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch_discussion(client, config, _STORY)

    assert max(most_in_flight) == 2


def test_fetch_discussion_rejects_a_response_for_another_item() -> None:
    comment = recorded_items()["47542672"]

    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=comment))) as client,
        pytest.raises(ValueError, match="47542553"),
    ):
        fetch_discussion(client, _CONFIG, _STORY)


def test_fetch_discussion_rejects_a_story_hacker_news_does_not_know() -> None:
    with _client({}, []) as client, pytest.raises(ValueError, match="no item 47542553"):
        fetch_discussion(client, _CONFIG, _STORY)


def test_fetch_discussion_raises_when_the_api_fails() -> None:
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        fetch_discussion(client, _CONFIG, _STORY)
