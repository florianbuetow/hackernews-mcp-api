"""Tests for saving each story's post and discussion files."""

import json
from pathlib import Path
from typing import Any

import httpx

from search_hackernews.algolia import Story
from search_hackernews.archive import Saved, StoryFiles, save_story
from search_hackernews.config import DiscussionsConfig
from tests.helpers import ARTICLE_PAGE, discussion_items, item_response, recorded_hit

_DISCUSSIONS = DiscussionsConfig(item_url="https://hacker-news.firebaseio.com/v0/item/{id}.json", max_concurrent_requests=4)
_LINK_STORY = Story.model_validate(recorded_hit("48900432"))


def _transport(requests: list[str], article: httpx.Response) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.host == "hacker-news.firebaseio.com":
            return item_response(discussion_items(48900432), request)
        return article

    return httpx.MockTransport(handler)


def _save(tmp_path: Path, story: Story, fetch_discussions: bool, requests: list[str], article: httpx.Response) -> StoryFiles:
    with httpx.Client(transport=_transport(requests, article)) as client:
        return save_story(client, _DISCUSSIONS, tmp_path, story, fetch_discussions)


def _article_page() -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html"}, text=ARTICLE_PAGE)


def test_save_story_writes_the_post_with_its_article_and_the_discussion(tmp_path: Path) -> None:
    requests: list[str] = []

    files = _save(tmp_path, _LINK_STORY, True, requests, _article_page())

    assert files == StoryFiles(post=Saved.WRITTEN, article_problem=None, discussion=Saved.WRITTEN)
    assert requests == [
        "https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers",
        "https://hacker-news.firebaseio.com/v0/item/48900432.json",
        "https://hacker-news.firebaseio.com/v0/item/48900433.json",
        "https://hacker-news.firebaseio.com/v0/item/48900434.json",
    ]
    assert "Forward deployed engineers sit with customers" in (tmp_path / "posts" / "48900432.md").read_text(encoding="utf-8")
    items = discussion_items(48900432)
    reply: dict[str, Any] = items["48900434"] | {"comments": []}
    discussion: dict[str, Any] = items["48900432"] | {"comments": [items["48900433"] | {"comments": [reply]}]}
    assert json.loads((tmp_path / "discussions" / "48900432.json").read_text(encoding="utf-8")) == discussion


def test_save_story_keeps_files_saved_by_an_earlier_run(tmp_path: Path) -> None:
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "48900432.md").write_text("earlier post\n", encoding="utf-8")
    (tmp_path / "discussions").mkdir()
    (tmp_path / "discussions" / "48900432.json").write_text("{}\n", encoding="utf-8")
    requests: list[str] = []

    files = _save(tmp_path, _LINK_STORY, True, requests, _article_page())

    assert files == StoryFiles(post=Saved.EXISTED, article_problem=None, discussion=Saved.EXISTED)
    assert requests == []
    assert (tmp_path / "posts" / "48900432.md").read_text(encoding="utf-8") == "earlier post\n"
    assert (tmp_path / "discussions" / "48900432.json").read_text(encoding="utf-8") == "{}\n"


def test_save_story_without_discussion_saves_only_the_post(tmp_path: Path) -> None:
    requests: list[str] = []

    files = _save(tmp_path, _LINK_STORY, False, requests, _article_page())

    assert files == StoryFiles(post=Saved.WRITTEN, article_problem=None, discussion=None)
    assert requests == ["https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers"]
    assert not (tmp_path / "discussions").exists()


def test_save_story_records_an_article_that_could_not_be_downloaded(tmp_path: Path) -> None:
    files = _save(tmp_path, _LINK_STORY, False, [], httpx.Response(403))

    assert files.article_problem == "HTTP 403 Forbidden"
    assert "Not downloaded: HTTP 403 Forbidden." in (tmp_path / "posts" / "48900432.md").read_text(encoding="utf-8")


def test_save_story_does_not_download_anything_for_a_text_post(tmp_path: Path) -> None:
    text_post = Story.model_validate(recorded_hit("47542553") | {"story_text": "We&#x27;re hiring.<p>Any advice?"})
    requests: list[str] = []

    files = _save(tmp_path, text_post, False, requests, _article_page())

    assert files == StoryFiles(post=Saved.WRITTEN, article_problem=None, discussion=None)
    assert requests == []
    assert "We're hiring.\n\nAny advice?" in (tmp_path / "posts" / "47542553.md").read_text(encoding="utf-8")
