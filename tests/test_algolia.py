"""Tests for fetching stories from the Algolia index behind hn.algolia.com."""

import json

import httpx
import pytest
from pydantic import ValidationError

from search_hackernews.algolia import Story, search_stories
from search_hackernews.config import AlgoliaConfig
from tests.helpers import recorded_hit, recorded_response, website_story_ids


def _config() -> AlgoliaConfig:
    return AlgoliaConfig(
        application_id="TESTAPP",
        api_key="test-key",
        index="Item_dev",
        params={"hitsPerPage": 1000, "tagFilters": ["story"], "queryType": "prefixNone"},
    )


def test_story_reads_an_empty_url_or_text_as_missing() -> None:
    story = Story.model_validate(recorded_hit("48900432") | {"url": "", "story_text": ""})

    assert story.url is None
    assert story.story_text is None


def test_search_stories_sends_the_query_with_the_configured_parameters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=recorded_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        search_stories(client, _config(), "Forward deployed engineers")

    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == "https://testapp-dsn.algolia.net/1/indexes/Item_dev/query"
    assert request.headers["X-Algolia-Application-Id"] == "TESTAPP"
    assert request.headers["X-Algolia-API-Key"] == "test-key"
    assert json.loads(request.content) == {
        "hitsPerPage": 1000,
        "tagFilters": ["story"],
        "queryType": "prefixNone",
        "query": "Forward deployed engineers",
        "page": 0,
    }


def test_search_stories_returns_the_stories_of_every_page_in_order() -> None:
    hits = recorded_response()["hits"]
    pages = [hits[:50], hits[50:]]

    def handler(request: httpx.Request) -> httpx.Response:
        page = json.loads(request.content)["page"]
        return httpx.Response(200, json=recorded_response() | {"hits": pages[page], "page": page, "nbPages": 2, "hitsPerPage": 50})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = search_stories(client, _config(), "Forward deployed engineers")

    assert [story.object_id for story in result.stories] == website_story_ids()
    assert result.total_matches == 73


def test_search_stories_raises_when_the_api_rejects_the_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Invalid Application-ID or API key", "status": 403})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(httpx.HTTPStatusError):
        search_stories(client, _config(), "Forward deployed engineers")


def test_search_stories_rejects_a_story_without_points() -> None:
    response = recorded_response()
    del response["hits"][0]["points"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(ValidationError):
        search_stories(client, _config(), "Forward deployed engineers")
