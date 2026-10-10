/**
 * MCP tools that search Hacker News posts and comments: text search through Algolia, since the
 * official Hacker News API has none, and the comments on one post through the official API.
 */

import { McpServer } from '@modelcontextprotocol/server';
import type { CallToolResult } from '@modelcontextprotocol/server';
import { z } from 'zod';

import { searchComments, searchPosts } from './algolia.ts';
import type { Config } from './config.ts';
import { searchPostComments } from './hackernews.ts';
import type { SearchPage } from './search.ts';

const SEARCH_ARGUMENTS = {
  query: z.string().describe('Words to search for; an empty string matches everything'),
  min_date: z.iso.date().optional().describe('Only items created on or after this day, YYYY-MM-DD (UTC)'),
  max_date: z.iso.date().optional().describe('Only items created on or before this day, YYYY-MM-DD (UTC)'),
  page: z.int().min(0).describe('Zero-based page of results'),
  hits_per_page: z.int().min(1).max(1000).describe('Results per page; only the first 1000 results of a search are reachable'),
};

const PAGE_DESCRIPTION = 'Returns JSON with total_matches, page, pages (the page count), and hits';

/** A server whose tools search Hacker News through fetchFn. */
export function createServer(config: Config, fetchFn: typeof fetch): McpServer {
  const server = new McpServer({ name: 'search-hackernews', version: '0.0.1' });
  server.registerTool(
    'search_posts',
    {
      description:
        'Search Hacker News posts (stories), ranked like the hn.algolia.com website. ' +
        `${PAGE_DESCRIPTION}: id, title, url, text (HTML, text posts only), hn_url, author, points, comments, created_at.`,
      inputSchema: z.object(SEARCH_ARGUMENTS),
    },
    async (request) => asJson(await searchPosts(fetchFn, config, request)),
  );
  server.registerTool(
    'search_comments',
    {
      description:
        'Search Hacker News comments on all posts. ' +
        `${PAGE_DESCRIPTION}: id, hn_url, author, text (HTML), post_id, post_title, parent_id, created_at.`,
      inputSchema: z.object(SEARCH_ARGUMENTS),
    },
    async (request) => asJson(await searchComments(fetchFn, config, request)),
  );
  server.registerTool(
    'search_post_comments',
    {
      description:
        'Search the comments on one Hacker News post, read live from the official Hacker News API, in thread order. ' +
        'A comment matches when its text contains every query word, ignoring case; an empty query lists all of them. ' +
        `${PAGE_DESCRIPTION}: id, hn_url, author, text (HTML), post_id, post_title, parent_id, created_at.`,
      inputSchema: z.object({
        post_id: z.string().regex(/^\d+$/).describe('The id of the post, as search_posts returns it'),
        ...SEARCH_ARGUMENTS,
      }),
    },
    async ({ post_id, ...request }) => asJson(await searchPostComments(fetchFn, config, post_id, request)),
  );
  return server;
}

function asJson(page: SearchPage<unknown>): CallToolResult {
  return { content: [{ type: 'text', text: JSON.stringify(page) }] };
}
