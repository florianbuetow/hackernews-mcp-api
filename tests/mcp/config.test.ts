import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, test } from 'node:test';

import { loadConfig } from '../../src/mcp/config.ts';

const SETTINGS = `
[http]
user_agent = "test-agent/1.0"
timeout_seconds = 5

[algolia]
application_id = "TESTAPP"
api_key = "test-key"
index = "Item_dev"

[algolia.params]
hitsPerPage = 1000
tagFilters = ["story"]

[discussions]
item_url = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
max_concurrent_requests = 8

[output]
directory = "data/output"
`;

const directory = mkdtempSync(join(tmpdir(), 'search-hackernews-config-'));
after(() => rmSync(directory, { recursive: true }));

function settingsFile(text: string): string {
  const path = join(directory, `${crypto.randomUUID()}.toml`);
  writeFileSync(path, text);
  return path;
}

test('reads the http, algolia, and discussions settings', () => {
  assert.deepEqual(loadConfig(settingsFile(SETTINGS)), {
    http: { user_agent: 'test-agent/1.0', timeout_seconds: 5 },
    algolia: {
      application_id: 'TESTAPP',
      api_key: 'test-key',
      index: 'Item_dev',
      params: { hitsPerPage: 1000, tagFilters: ['story'] },
    },
    discussions: { item_url: 'https://hacker-news.firebaseio.com/v0/item/{id}.json', max_concurrent_requests: 8 },
  });
});

test('rejects a missing setting', () => {
  assert.throws(() => loadConfig(settingsFile(SETTINGS.replace('timeout_seconds = 5\n', ''))), /timeout_seconds/);
});

test('rejects an unknown setting', () => {
  assert.throws(() => loadConfig(settingsFile(SETTINGS.replace('index = "Item_dev"', 'index = "Item_dev"\nreplicas = "Item_dev_sort_date"'))), /replicas/);
});

test("accepts the project's config/search.toml", () => {
  loadConfig(join(import.meta.dirname, '..', '..', 'config', 'search.toml'));
});
