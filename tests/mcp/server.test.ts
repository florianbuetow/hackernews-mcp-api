import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/client';
import { InMemoryTransport } from '@modelcontextprotocol/server';

import { createServer } from '../../src/mcp/server.ts';
import { CONFIG, POST_COMMENTS, POSTS, fakeFetch, itemsFetch, recordedFetch, recordedItems } from './helpers.ts';

/** A client connected in memory to a server that searches through fetchFn. */
async function connect(fetchFn: typeof fetch): Promise<Client> {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await createServer(CONFIG, fetchFn).connect(serverTransport);
  const client = new Client({ name: 'test-client', version: '1.0.0' });
  await client.connect(clientTransport);
  return client;
}

/** The JSON a successful tool call returned. */
function json(result: Awaited<ReturnType<Client['callTool']>>): { total_matches: number; hits: Record<string, unknown>[] } {
  assert.equal(result.isError, undefined, JSON.stringify(result.content));
  const [content] = result.content;
  assert.equal(content?.type, 'text');
  return JSON.parse(content.text);
}

test('lists the three search tools with their required arguments', async () => {
  const client = await connect(recordedFetch(POSTS).fetch);

  const { tools } = await client.listTools();

  assert.deepEqual(Object.fromEntries(tools.map((tool) => [tool.name, tool.inputSchema.required?.toSorted()])), {
    search_posts: ['hits_per_page', 'page', 'query'],
    search_comments: ['hits_per_page', 'page', 'query'],
    search_post_comments: ['hits_per_page', 'page', 'post_id', 'query'],
  });
});

test('search_posts returns the matching posts as JSON', async () => {
  const { fetch, requests } = recordedFetch(POSTS);
  const client = await connect(fetch);

  const result = await client.callTool({
    name: 'search_posts',
    arguments: { query: 'Forward deployed engineers', min_date: '2025-01-01', page: 0, hits_per_page: 100 },
  });

  const page = json(result);
  assert.equal(page.total_matches, 73);
  assert.equal(page.hits[0]?.['id'], '48900432');
  assert.deepEqual(requests[0]?.body, {
    hitsPerPage: 100,
    tagFilters: ['story'],
    queryType: 'prefixNone',
    query: 'Forward deployed engineers',
    page: 0,
    numericFilters: ['created_at_i>=1735689600'],
  });
});

test('search_comments searches all comments', async () => {
  const { fetch, requests } = recordedFetch(POST_COMMENTS);
  const client = await connect(fetch);

  const result = await client.callTool({
    name: 'search_comments',
    arguments: { query: 'palantir', max_date: '2026-12-31', page: 1, hits_per_page: 3 },
  });

  assert.equal(json(result).hits[0]?.['id'], '48933929');
  const body = requests[0]?.body as Record<string, unknown>;
  assert.deepEqual(
    { query: body['query'], page: body['page'], hitsPerPage: body['hitsPerPage'], tagFilters: body['tagFilters'], numericFilters: body['numericFilters'] },
    { query: 'palantir', page: 1, hitsPerPage: 3, tagFilters: ['comment'], numericFilters: ['created_at_i<1798761600'] },
  );
});

test("search_post_comments reads the post's comments from the official Hacker News API", async () => {
  const { fetch, requests } = itemsFetch(recordedItems());
  const client = await connect(fetch);

  const result = await client.callTool({
    name: 'search_post_comments',
    arguments: { post_id: '47542553', query: 'palantir', page: 0, hits_per_page: 10 },
  });

  const page = json(result);
  assert.equal(page.total_matches, 2);
  assert.deepEqual(
    page.hits.map((hit) => hit['id']),
    ['47543168', '47545725'],
  );
  assert.equal(requests.length, 8);
  assert.ok(requests.every((request) => request.url.startsWith('https://hacker-news.firebaseio.com/v0/item/')));
});

for (const [name, args] of [
  ['a date that is not YYYY-MM-DD', { query: 'rust', min_date: '2025-1-1', page: 0, hits_per_page: 10 }],
  ['a day that does not exist', { query: 'rust', max_date: '2025-02-30', page: 0, hits_per_page: 10 }],
  ['a negative page', { query: 'rust', page: -1, hits_per_page: 10 }],
  ['more than 1000 hits per page', { query: 'rust', page: 0, hits_per_page: 1001 }],
  ['a missing page', { query: 'rust', hits_per_page: 10 }],
] as const) {
  test(`search_posts rejects ${name}, without searching`, async () => {
    const { fetch, requests } = recordedFetch(POSTS);
    const client = await connect(fetch);

    const result = await client.callTool({ name: 'search_posts', arguments: args });

    assert.equal(result.isError, true);
    assert.equal(requests.length, 0);
  });
}

test('search_post_comments rejects a post id that is not a number, without searching', async () => {
  const { fetch, requests } = recordedFetch(POST_COMMENTS);
  const client = await connect(fetch);

  const result = await client.callTool({
    name: 'search_post_comments',
    arguments: { post_id: 'story_48900432', query: '', page: 0, hits_per_page: 3 },
  });

  assert.equal(result.isError, true);
  assert.equal(requests.length, 0);
});

test('reports a failed search as a tool error', async () => {
  const { fetch } = fakeFetch(async () => new Response('Service Unavailable', { status: 503 }));
  const client = await connect(fetch);

  const result = await client.callTool({ name: 'search_posts', arguments: { query: 'rust', page: 0, hits_per_page: 10 } });

  assert.equal(result.isError, true);
  assert.match(JSON.stringify(result.content), /HTTP 503/);
});
