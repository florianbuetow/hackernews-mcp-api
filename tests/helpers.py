"""Test data recorded on 2026-10-10 for the example query "Forward deployed engineers"."""

import json
from pathlib import Path
from typing import Any

import httpx

_FIXTURES = Path(__file__).parent / "fixtures"

# A news article page with navigation and footer around the article body.
ARTICLE_PAGE = """<!doctype html>
<html>
<head><title>Why forward deployed engineers matter</title></head>
<body>
<nav><a href="/">Home</a> <a href="/about">About</a> <a href="/subscribe">Subscribe</a></nav>
<article>
<h1>Why forward deployed engineers matter</h1>
<p>Forward deployed engineers sit with customers and turn their problems into working software within days rather than months.</p>
<p>The role started at Palantir, where engineers were embedded with analysts to adapt the platform to each mission on site.</p>
<p>Today AI startups hire them to bridge the gap between a general model and the messy workflows of a specific enterprise.</p>
</article>
<footer>Copyright 2026 Example News. All rights reserved.</footer>
</body>
</html>
"""


def recorded_response() -> dict[str, Any]:
    """Algolia's response to the request hn.algolia.com sends for the example query (story texts removed)."""
    response: dict[str, Any] = json.loads((_FIXTURES / "forward_deployed_engineers_response.json").read_text(encoding="utf-8"))
    return response


def recorded_hit(object_id: str) -> dict[str, Any]:
    """One story from the recorded response."""
    hit: dict[str, Any] = next(hit for hit in recorded_response()["hits"] if hit["objectID"] == object_id)
    return hit


def website_story_ids() -> list[str]:
    """Story IDs in the order hn.algolia.com displayed them for the example query."""
    return (_FIXTURES / "forward_deployed_engineers_website_ids.txt").read_text(encoding="utf-8").split()


def discussion_items(story_id: int) -> dict[str, dict[str, Any]]:
    """A story with a two-level comment tree, by ID, each item shaped like the official Hacker News API serves it."""
    story: dict[str, Any] = {
        "by": "saisrirampur",
        "descendants": 2,
        "id": story_id,
        "kids": [story_id + 1],
        "score": 106,
        "time": 1783985950,
        "title": "What are Forward Deployed Engineers, and why are they so in demand? (2025)",
        "type": "story",
        "url": "https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers",
    }
    comment: dict[str, Any] = {
        "by": "alice",
        "id": story_id + 1,
        "kids": [story_id + 2],
        "parent": story_id,
        "text": "<p>Isn&#x27;t this just solutions engineering?</p>",
        "time": 1784016000,
        "type": "comment",
    }
    reply: dict[str, Any] = {
        "by": "bob",
        "id": story_id + 2,
        "parent": story_id + 1,
        "text": "<p>Agreed, it&#x27;s consulting with commit access.</p>",
        "time": 1784021400,
        "type": "comment",
    }
    return {str(item["id"]): item for item in (story, comment, reply)}


def recorded_items() -> dict[str, dict[str, Any]]:
    """Story 47542553 and its 7 comments, by ID, as the official Hacker News API served them on 2026-10-11."""
    items: dict[str, dict[str, Any]] = json.loads((_FIXTURES / "ask_hn_forward_deployed_engineers_items.json").read_text(encoding="utf-8"))
    return items


def item_response(items: dict[str, dict[str, Any]], request: httpx.Request) -> httpx.Response:
    """Answer a request for an item like the official Hacker News API, which sends null for an unknown ID."""
    item_id = request.url.path.removeprefix("/v0/item/").removesuffix(".json")
    if item_id not in items:
        return httpx.Response(200, content=b"null", headers={"content-type": "application/json"})
    return httpx.Response(200, json=items[item_id])
