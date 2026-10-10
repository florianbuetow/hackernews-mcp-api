"""Hacker News story search through the Algolia index behind hn.algolia.com."""

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, field_validator

from search_hackernews.config import AlgoliaConfig


class Story(BaseModel):
    """A Hacker News story from the search results."""

    object_id: str = Field(alias="objectID")
    title: str
    url: str | None = None  # text posts such as "Ask HN" have no url
    story_text: str | None = None  # HTML; only text posts have one
    author: str
    points: int
    num_comments: int
    created_at_i: int

    @field_validator("url", "story_text")
    @classmethod
    def _empty_means_missing(cls, value: str | None) -> str | None:
        """Algolia sends an empty string instead of leaving the field out for some stories."""
        if value == "":
            return None
        return value


class _SearchPage(BaseModel):
    """One page of search results."""

    hits: list[Story]
    nb_hits: int = Field(alias="nbHits")
    nb_pages: int = Field(alias="nbPages")


@dataclass(frozen=True)
class SearchResult:
    """The stories a search returned, in ranking order, and how many stories matched."""

    stories: list[Story]
    total_matches: int


def search_stories(client: httpx.Client, config: AlgoliaConfig, query: str) -> SearchResult:
    """Fetch every page of stories matching the query."""
    first_page = _fetch_page(client, config, query, 0)
    stories = list(first_page.hits)
    for page in range(1, first_page.nb_pages):
        stories.extend(_fetch_page(client, config, query, page).hits)
    return SearchResult(stories=stories, total_matches=first_page.nb_hits)


def _fetch_page(client: httpx.Client, config: AlgoliaConfig, query: str, page: int) -> _SearchPage:
    """Fetch one page of search results."""
    response = client.post(
        f"https://{config.application_id}-dsn.algolia.net/1/indexes/{config.index}/query",
        headers={"X-Algolia-Application-Id": config.application_id, "X-Algolia-API-Key": config.api_key},
        json={**config.params, "query": query, "page": page},
    )
    response.raise_for_status()
    return _SearchPage.model_validate_json(response.content)
