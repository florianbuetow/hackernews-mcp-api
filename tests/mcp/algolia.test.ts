import assert from 'node:assert/strict';
import { test } from 'node:test';

import { searchComments, searchPosts } from '../../src/mcp/algolia.ts';
import { CONFIG, POST_COMMENTS, POSTS, fakeFetch, recordedFetch, recordedResponse } from './helpers.ts';

const POST_TITLE = 'What are Forward Deployed Engineers, and why are they so in demand? (2025)';

test('searchPosts sends the configured parameters with the query, page, hits per page, and story tag', async () => {
  const { fetch, requests } = recordedFetch(POSTS);

  await searchPosts(fetch, CONFIG, { query: 'Forward deployed engineers', page: 2, hits_per_page: 20 });

  assert.equal(requests.length, 1);
  const [request] = requests;
  assert.equal(request?.url, 'https://TESTAPP-dsn.algolia.net/1/indexes/Item_dev/query');
  assert.equal(request?.method, 'POST');
  assert.equal(request?.headers.get('X-Algolia-Application-Id'), 'TESTAPP');
  assert.equal(request?.headers.get('X-Algolia-API-Key'), 'test-key');
  assert.equal(request?.headers.get('User-Agent'), 'test-agent/1.0');
  assert.deepEqual(request?.body, {
    hitsPerPage: 20,
    tagFilters: ['story'],
    queryType: 'prefixNone',
    query: 'Forward deployed engineers',
    page: 2,
    numericFilters: [],
  });
});

for (const [dates, filters] of [
  [{ min_date: '2025-01-01', max_date: '2025-12-31' }, ['created_at_i>=1735689600', 'created_at_i<1767225600']],
  [{ min_date: '2025-01-01' }, ['created_at_i>=1735689600']],
  [{ max_date: '2025-12-31' }, ['created_at_i<1767225600']],
  [{ min_date: '2024-02-29', max_date: '2024-02-29' }, ['created_at_i>=1709164800', 'created_at_i<1709251200']],
] as const) {
  test(`dates ${JSON.stringify(dates)} keep items created on and between those UTC days`, async () => {
    const { fetch, requests } = recordedFetch(POSTS);

    await searchPosts(fetch, CONFIG, { query: 'rust', page: 0, hits_per_page: 10, ...dates });

    assert.deepEqual((requests[0]?.body as { numericFilters: unknown }).numericFilters, filters);
  });
}

test('searchComments searches the comment tag', async () => {
  const { fetch, requests } = recordedFetch(POST_COMMENTS);

  await searchComments(fetch, CONFIG, { query: 'palantir', page: 0, hits_per_page: 3 });

  assert.deepEqual((requests[0]?.body as { tagFilters: unknown }).tagFilters, ['comment']);
});

test('searchPosts returns the page of posts with links and counts', async () => {
  const page = await searchPosts(recordedFetch(POSTS).fetch, CONFIG, { query: 'Forward deployed engineers', page: 0, hits_per_page: 1000 });

  assert.equal(page.total_matches, 73);
  assert.equal(page.page, 0);
  assert.equal(page.pages, 1);
  assert.equal(page.hits.length, 73);
  assert.deepEqual(page.hits[0], {
    id: '48900432',
    title: POST_TITLE,
    url: 'https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers',
    text: null,
    hn_url: 'https://news.ycombinator.com/item?id=48900432',
    author: 'saisrirampur',
    points: 106,
    comments: 98,
    created_at: '2026-07-13T23:39:10Z',
  });
});

test('a post without a link, or with an empty one, has no url', async () => {
  const page = await searchPosts(recordedFetch(POSTS).fetch, CONFIG, { query: 'Forward deployed engineers', page: 0, hits_per_page: 1000 });

  const withoutLink = page.hits.find((post) => post.id === '47542553');
  const emptyLink = page.hits.find((post) => post.id === '3994605');
  assert.equal(withoutLink?.url, null);
  assert.equal(emptyLink?.url, null);
});

test('a text post returns its text', async () => {
  const response = recordedResponse(POSTS);
  const textPost = { ...response.hits[1], story_text: '<p>What do they do all day?</p>' };
  const { fetch } = fakeFetch(async () => Response.json({ ...response, hits: [textPost] }));

  const page = await searchPosts(fetch, CONFIG, { query: 'Forward deployed engineers', page: 0, hits_per_page: 1000 });

  assert.equal(page.hits[0]?.text, '<p>What do they do all day?</p>');
});

test('searchComments returns the page of comments with their post', async () => {
  const recorded = recordedResponse(POST_COMMENTS);

  const page = await searchComments(recordedFetch(POST_COMMENTS).fetch, CONFIG, { query: '', page: 0, hits_per_page: 3 });

  assert.equal(page.total_matches, 98);
  assert.equal(page.page, 0);
  assert.equal(page.pages, 33);
  assert.deepEqual(page.hits[2], {
    id: '48914009',
    hn_url: 'https://news.ycombinator.com/item?id=48914009',
    author: 'altairprime',
    text: recorded.hits[2]?.['comment_text'],
    post_id: '48900432',
    post_title: POST_TITLE,
    parent_id: '48900432',
    created_at: '2026-07-14T22:58:55Z',
  });
});

test('rejects a page that starts past the first 1000 hits, without searching', async () => {
  const { fetch, requests } = recordedFetch(POSTS);

  await assert.rejects(searchPosts(fetch, CONFIG, { query: 'rust', page: 10, hits_per_page: 100 }), /first 1000 hits/);
  assert.equal(requests.length, 0);
});

test('accepts the last page within the first 1000 hits', async () => {
  const { fetch, requests } = recordedFetch(POSTS);

  await searchPosts(fetch, CONFIG, { query: 'rust', page: 9, hits_per_page: 100 });

  assert.equal(requests.length, 1);
});

test('rejects min_date after max_date, without searching', async () => {
  const { fetch, requests } = recordedFetch(POSTS);

  await assert.rejects(
    searchPosts(fetch, CONFIG, { query: 'rust', min_date: '2025-02-01', max_date: '2025-01-31', page: 0, hits_per_page: 10 }),
    /min_date 2025-02-01 is after max_date 2025-01-31/,
  );
  assert.equal(requests.length, 0);
});

test('fails when Algolia answers with an HTTP error', async () => {
  const { fetch } = fakeFetch(async () => new Response('{"message":"Invalid Application-ID or API key","status":403}', { status: 403 }));

  await assert.rejects(searchPosts(fetch, CONFIG, { query: 'rust', page: 0, hits_per_page: 10 }), /HTTP 403.*Invalid Application-ID/);
});

test('fails when Algolia answers with an unexpected body', async () => {
  const { fetch } = fakeFetch(async () => Response.json({ message: 'not a search result' }));

  await assert.rejects(searchPosts(fetch, CONFIG, { query: 'rust', page: 0, hits_per_page: 10 }), /nbHits/);
});

test('gives up when Algolia does not answer within the configured timeout', async () => {
  const { fetch } = fakeFetch(
    (_url, init) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
      }),
  );
  const config = { ...CONFIG, http: { ...CONFIG.http, timeout_seconds: 0.05 } };

  await assert.rejects(searchPosts(fetch, config, { query: 'rust', page: 0, hits_per_page: 10 }), { name: 'TimeoutError' });
});
