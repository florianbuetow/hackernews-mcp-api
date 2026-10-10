"""Save each story's post and discussion next to the search results."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

from search_hackernews.algolia import Story
from search_hackernews.articles import ArticleUnavailable, fetch_article
from search_hackernews.config import DiscussionsConfig
from search_hackernews.discussions import fetch_discussion
from search_hackernews.output import discussion_file, post_file, render_post


class Saved(Enum):
    """Whether this run wrote a file or kept the one an earlier run wrote."""

    WRITTEN = "saved"
    EXISTED = "already saved"


@dataclass(frozen=True)
class StoryFiles:
    """What happened to one story's files."""

    post: Saved
    article_problem: str | None  # why the post lacks the linked page's text
    discussion: Saved | None  # None when the discussion was not requested


def save_story(client: httpx.Client, discussions: DiscussionsConfig, directory: Path, story: Story, fetch_discussions: bool) -> StoryFiles:
    """Save the story's post and, if requested, its discussion, keeping files an earlier run saved."""
    post, article_problem = _save_post(client, directory / post_file(story), story)
    discussion = _save_discussion(client, discussions, directory / discussion_file(story), story) if fetch_discussions else None
    return StoryFiles(post=post, article_problem=article_problem, discussion=discussion)


def _save_post(client: httpx.Client, path: Path, story: Story) -> tuple[Saved, str | None]:
    """Write the post with the text of the page it links to; return what happened and why that text is missing."""
    if path.exists():
        return Saved.EXISTED, None
    article = None if story.url is None else fetch_article(client, story.url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_post(story, article), encoding="utf-8")
    if isinstance(article, ArticleUnavailable):
        return Saved.WRITTEN, article.reason
    return Saved.WRITTEN, None


def _save_discussion(client: httpx.Client, config: DiscussionsConfig, path: Path, story: Story) -> Saved:
    """Write the story's comment tree as JSON."""
    if path.exists():
        return Saved.EXISTED
    discussion = fetch_discussion(client, config, story.object_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(discussion, encoding="utf-8")
    return Saved.WRITTEN
