# Hackernews MCP and API

Search Hacker News posts and comments from the command line or from AI agents such as
Claude Code.

- **CLI** (Python) searches stories and saves the results, each story's linked article,
  and its full discussion as files.
- **MCP server** (TypeScript) gives AI agents tools to search posts, comments, and the
  comments on one post, filtered by date.

Discussions come from the [official Hacker News API](https://github.com/HackerNews/API).
Because it has no search, text search uses [Algolia](https://hn.algolia.com/), the search
Hacker News links to.

## Quickstart

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just),
and Node.js 22.18+.

```bash
git clone https://github.com/florianbuetow/hackernews-mcp-api.git
cd hackernews-mcp-api
uv run --all-extras pre-commit install
just init
npm ci
```

Search from the command line:

```bash
just search "forward deployed engineers"
```

Add the MCP server to Claude Code, for all your sessions:

```bash
claude mcp add --scope user hackernews -- node "$PWD/src/mcp/main.ts"
```

## CLI

A search saves its results to `data/output/YYYY-MM-DD-<query>/`:

- `results.md`: the matching stories
- `posts/<id>.md`: each story with the text of the page it links to
- `discussions/<id>.json`: each story's comments

Add `--no-discussion` to skip the comments. Searching the same query again on the same day
is skipped; delete its folder to run it again.

## MCP Server

- `search_posts` searches posts.
- `search_comments` searches comments on all posts.
- `search_post_comments` searches the comments on one post.

All three can filter by date.

## Configuration

Settings live in `config/search.toml`.

## Development

```bash
just help           # all commands
just ci             # all Python checks and tests
npm test            # MCP server tests
npm run typecheck   # MCP server type check
```

Development rules for contributors and AI agents are in [AGENTS.md](AGENTS.md).

## Project Structure

```
hackernews-mcp-api/
├── src/search_hackernews/   # Python CLI (entry point: src/main.py)
├── src/mcp/                 # TypeScript MCP server
├── tests/                   # Tests; MCP server tests in tests/mcp/
├── config/                  # Settings and checker rules
├── scripts/                 # Utility scripts
└── data/output/             # Saved searches (not in git)
```

## License

MIT, see [LICENCE](LICENCE).
