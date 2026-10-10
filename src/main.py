"""Search Hacker News stories and save the query, the results, and each story's post and discussion."""

import sys
from collections import Counter
from datetime import date
from pathlib import Path

import httpx

from search_hackernews.algolia import search_stories
from search_hackernews.archive import Saved, StoryFiles, save_story
from search_hackernews.config import load_config
from search_hackernews.output import directory_name, render_query, render_results


def main(argv: list[str], project_root: Path, today: date, transport: httpx.BaseTransport) -> int:
    """Search for the query in argv and save everything it finds; return the exit code.

    argv holds the query and optionally --no-discussion, which skips downloading comment trees.
    """
    fetch_discussions = "--no-discussion" not in argv
    args = [arg for arg in argv if arg != "--no-discussion"]
    if len(args) != 1 or not args[0].strip() or args[0].startswith("--"):
        print('Usage: just search "<query>" [--no-discussion]', file=sys.stderr)
        return 1
    query = args[0]
    config = load_config(project_root / "config" / "search.toml")
    directory = project_root / config.output.directory / directory_name(query, today)
    results_path = directory / "results.md"
    if results_path.exists():
        print(f"Skipped: {results_path} already exists. Delete it to search again.")
        return 0
    headers = {"User-Agent": config.http.user_agent}
    with httpx.Client(transport=transport, timeout=config.http.timeout_seconds, follow_redirects=True, headers=headers) as client:
        result = search_stories(client, config.algolia, query)
        print(f"Found {len(result.stories)} of {result.total_matches} matching stories")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "query.md").write_text(render_query(query), encoding="utf-8")
        saved: list[StoryFiles] = []
        for rank, story in enumerate(result.stories, start=1):
            files = save_story(client, config.discussions, directory, story, fetch_discussions)
            print(f"[{rank}/{len(result.stories)}] {story.object_id}: {_describe(files)}")
            saved.append(files)
    results_path.write_text(render_results(query, result, fetch_discussions), encoding="utf-8")
    _print_summary(directory, saved, fetch_discussions)
    return 0


def _describe(files: StoryFiles) -> str:
    """Say what happened to one story's files."""
    description = f"post {files.post.value}"
    if files.article_problem is not None:
        description += f" without article text ({files.article_problem})"
    if files.discussion is not None:
        description += f", discussion {files.discussion.value}"
    return description


def _print_summary(directory: Path, saved: list[StoryFiles], fetch_discussions: bool) -> None:
    """Report the saved, kept, and incomplete files of the whole search."""
    posts = Counter(files.post for files in saved)
    without_article = sum(files.article_problem is not None for files in saved)
    print(f"Saved to {directory}")
    print(f"Posts: {posts[Saved.WRITTEN]} saved ({without_article} without article text), {posts[Saved.EXISTED]} already saved")
    if fetch_discussions:
        discussions = Counter(files.discussion for files in saved)
        print(f"Discussions: {discussions[Saved.WRITTEN]} saved, {discussions[Saved.EXISTED]} already saved")
    else:
        print("Discussions: not downloaded (--no-discussion)")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], Path(__file__).resolve().parent.parent, date.today(), httpx.HTTPTransport()))
