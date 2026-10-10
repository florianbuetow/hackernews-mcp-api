"""End-to-end tests for `just search` with the example query and its recorded response."""

import json
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.main import main
from tests.helpers import ARTICLE_PAGE, discussion_items, item_response, recorded_response, website_story_ids

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_QUERY = "Forward deployed engineers"
_DAY = date(2026, 10, 10)
_SEARCH_HOST = "uj5wyc0l7x-dsn.algolia.net"
_DISCUSSION_HOST = "hacker-news.firebaseio.com"
# The search parameters hn.algolia.com sends for
# https://hn.algolia.com/?dateRange=all&page=0&prefix=false&query=Forward%20deployed%20engineers&sort=byPopularity&type=story
_WEBSITE_SEARCH = {
    "query": _QUERY,
    "page": 0,
    "hitsPerPage": 1000,
    "tagFilters": ["story"],
    "queryType": "prefixNone",
    "typoTolerance": True,
    "minWordSizefor1Typo": 4,
    "minWordSizefor2Typos": 8,
    "ignorePlurals": False,
    "minProximity": 7,
    "advancedSyntax": True,
    "restrictSearchableAttributes": ["title", "comment_text", "url", "story_text", "author"],
}
# The recorded response has 73 stories: 48 link to a web page, 25 are text posts.
_LINKED_PAGES = 48


def _project(tmp_path: Path) -> Path:
    """Create a project root that uses the real search settings and writes its output under tmp_path."""
    (tmp_path / "config").mkdir()
    shutil.copy(_PROJECT_ROOT / "config" / "search.toml", tmp_path / "config" / "search.toml")
    return tmp_path


def _internet(requests: list[httpx.Request], search: dict[str, Any]) -> httpx.MockTransport:
    """Answer the search, the discussion downloads, and every linked page."""
    discussions = {item_id: item for story_id in website_story_ids() for item_id, item in discussion_items(int(story_id)).items()}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == _SEARCH_HOST:
            return httpx.Response(200, json=search)
        if request.url.host == _DISCUSSION_HOST:
            return item_response(discussions, request)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=ARTICLE_PAGE)

    return httpx.MockTransport(handler)


def _hosts(requests: list[httpx.Request]) -> list[str]:
    return [request.url.host for request in requests]


def test_search_saves_the_query_results_posts_and_discussions(tmp_path: Path) -> None:
    root = _project(tmp_path)
    search = recorded_response()
    ask_hn = next(hit for hit in search["hits"] if hit["objectID"] == "47542553")
    ask_hn["story_text"] = "We&#x27;re hiring Forward Deployed Engineers.<p>What are you seeing?"
    requests: list[httpx.Request] = []

    exit_code = main([_QUERY], root, _DAY, _internet(requests, search))

    assert exit_code == 0
    assert json.loads(requests[0].content) == _WEBSITE_SEARCH
    assert _hosts(requests).count(_DISCUSSION_HOST) == 73 * 3
    assert len(requests) == 1 + 73 * 3 + _LINKED_PAGES
    directory = root / "data" / "output" / "2026-10-10-Forward_deployed_engineers"
    assert (directory / "query.md").read_text(encoding="utf-8") == "# Query\n\nForward deployed engineers\n"
    results = (directory / "results.md").read_text(encoding="utf-8")
    assert re.findall(r"\| \[\d+\]\(https://news\.ycombinator\.com/item\?id=(\d+)\) \|", results) == website_story_ids()
    assert '73 stories for "Forward deployed engineers".' in results
    assert sorted(path.stem for path in (directory / "posts").iterdir()) == sorted(website_story_ids())
    assert sorted(path.stem for path in (directory / "discussions").iterdir()) == sorted(website_story_ids())
    link_post = (directory / "posts" / "48900432.md").read_text(encoding="utf-8")
    assert "Forward deployed engineers sit with customers" in link_post
    text_post = (directory / "posts" / "47542553.md").read_text(encoding="utf-8")
    assert "We're hiring Forward Deployed Engineers.\n\nWhat are you seeing?" in text_post
    discussion = json.loads((directory / "discussions" / "48900432.json").read_text(encoding="utf-8"))
    assert discussion["comments"][0]["comments"][0]["by"] == "bob"


def test_search_with_no_discussion_saves_the_posts_only(tmp_path: Path) -> None:
    root = _project(tmp_path)
    requests: list[httpx.Request] = []

    exit_code = main([_QUERY, "--no-discussion"], root, _DAY, _internet(requests, recorded_response()))

    assert exit_code == 0
    assert _DISCUSSION_HOST not in _hosts(requests)
    directory = root / "data" / "output" / "2026-10-10-Forward_deployed_engineers"
    assert len(list((directory / "posts").iterdir())) == 73
    assert not (directory / "discussions").exists()
    assert "discussions/" not in (directory / "results.md").read_text(encoding="utf-8")


def test_search_reports_a_linked_page_it_could_not_download(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _project(tmp_path)
    internet = _internet([], recorded_response())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.ft.com":
            return httpx.Response(403)
        return internet.handle_request(request)

    exit_code = main([_QUERY, "--no-discussion"], root, _DAY, httpx.MockTransport(handler))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "[2/73] 45788526: post saved without article text (HTTP 403 Forbidden)\n" in output
    assert "Posts: 73 saved (1 without article text), 0 already saved\n" in output
    post = root / "data" / "output" / "2026-10-10-Forward_deployed_engineers" / "posts" / "45788526.md"
    assert post.read_text(encoding="utf-8").endswith("## Article\n\nNot downloaded: HTTP 403 Forbidden.\n")


def test_search_skips_a_query_already_saved_today(tmp_path: Path) -> None:
    root = _project(tmp_path)
    results_path = root / "data" / "output" / "2026-10-10-Forward_deployed_engineers" / "results.md"
    results_path.parent.mkdir(parents=True)
    results_path.write_text("earlier results\n", encoding="utf-8")
    requests: list[httpx.Request] = []

    exit_code = main([_QUERY], root, _DAY, _internet(requests, recorded_response()))

    assert exit_code == 0
    assert requests == []
    assert results_path.read_text(encoding="utf-8") == "earlier results\n"


@pytest.mark.parametrize(
    "argv",
    [[], [""], ["   "], [_QUERY, "extra"], ["--no-discussion"], [_QUERY, "--no-comments"]],
    ids=["none", "empty", "blank", "two", "flag-only", "unknown-flag"],
)
def test_search_rejects_a_missing_query_or_unknown_argument(tmp_path: Path, argv: list[str]) -> None:
    root = _project(tmp_path)
    requests: list[httpx.Request] = []

    exit_code = main(argv, root, _DAY, _internet(requests, recorded_response()))

    assert exit_code == 1
    assert requests == []
    assert not (root / "data").exists()


def test_search_saves_nothing_when_the_search_request_fails(tmp_path: Path) -> None:
    root = _project(tmp_path)
    error = {"message": "Invalid Application-ID or API key", "status": 403}
    rejection = httpx.MockTransport(lambda request: httpx.Response(403, json=error))

    with pytest.raises(httpx.HTTPStatusError):
        main([_QUERY], root, _DAY, rejection)

    assert not (root / "data").exists()
