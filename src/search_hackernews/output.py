"""Folder layout and Markdown files of a saved search."""

import re
from datetime import UTC, date, datetime
from urllib.parse import quote

from markdownify import markdownify

from search_hackernews.algolia import SearchResult, Story
from search_hackernews.articles import Article, ArticleUnavailable


def directory_name(query: str, day: date) -> str:
    """Name the folder of a search: YYYY-MM-DD-<query with each non-alphanumeric character replaced by an underscore>."""
    return f"{day.isoformat()}-{re.sub(r'[^A-Za-z0-9]', '_', query)}"


def post_file(story: Story) -> str:
    """Path of the story's post, relative to the search folder."""
    return f"posts/{story.object_id}.md"


def discussion_file(story: Story) -> str:
    """Path of the story's comment tree, relative to the search folder."""
    return f"discussions/{story.object_id}.json"


def render_query(query: str) -> str:
    """Render query.md."""
    return f"# Query\n\n{_escape(query)}\n"


def render_results(query: str, result: SearchResult, with_discussions: bool) -> str:
    """Render results.md: one table row per story, in ranking order, linking the saved files."""
    returned = len(result.stories)
    if returned < result.total_matches:
        summary = f'{returned} of {result.total_matches} matching stories for "{_escape(query)}" (the search returns no more per query).'
    else:
        summary = f'{returned} stories for "{_escape(query)}".'
    header = ["# Results", "", summary, "", "| # | Title | Points | Comments | Author | Date | Saved |", "|---:|---|---:|---:|---|---|---|"]
    rows = [_row(rank, story, with_discussions) for rank, story in enumerate(result.stories, start=1)]
    return "\n".join([*header, *rows]) + "\n"


def render_post(story: Story, article: Article | ArticleUnavailable | None) -> str:
    """Render a post: the story's details, its own text, and the text of the page it links to."""
    lines = [f"# {_escape(story.title)}", ""]
    if story.url is not None:
        lines.append(f"- Link: <{_escape_url(story.url)}>")
    lines += [
        f"- Discussion: <{_discussion_url(story)}>",
        f"- Points: {story.points}",
        f"- Comments: {story.num_comments}",
        f"- Author: {_escape(story.author)}",
        f"- Date: {_posted(story)}",
    ]
    if story.story_text is not None:
        lines += ["", "## Text", "", markdownify(story.story_text).strip()]
    if isinstance(article, Article):
        lines += ["", "## Article", "", article.markdown.strip()]
    if isinstance(article, ArticleUnavailable):
        lines += ["", "## Article", "", f"Not downloaded: {article.reason}."]
    return "\n".join(lines) + "\n"


def _row(rank: int, story: Story, with_discussions: bool) -> str:
    """Render one story as a table row; text posts link their title to the discussion."""
    discussion = _discussion_url(story)
    link = discussion if story.url is None else _escape_url(story.url)
    saved = f"[post]({post_file(story)})"
    if with_discussions:
        saved += f" · [discussion]({discussion_file(story)})"
    return (
        f"| {rank} | [{_escape(story.title)}]({link}) | {story.points} "
        f"| [{story.num_comments}]({discussion}) | {_escape(story.author)} | {_posted(story)} | {saved} |"
    )


def _discussion_url(story: Story) -> str:
    """The story's page on Hacker News."""
    return f"https://news.ycombinator.com/item?id={story.object_id}"


def _posted(story: Story) -> str:
    """The day the story was posted, in UTC."""
    return datetime.fromtimestamp(story.created_at_i, tz=UTC).date().isoformat()


def _escape(text: str) -> str:
    """Backslash-escape characters Markdown would read as formatting, links, HTML, or table cells."""
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def _escape_url(url: str) -> str:
    """Percent-encode characters, such as spaces and parentheses, that would end a Markdown link."""
    return quote(url, safe=":/?#[]@!$&'*+,;=%~")
