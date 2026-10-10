import assert from 'node:assert/strict';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';

test('serves the search tools over stdio, from any working directory', async () => {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [join(import.meta.dirname, '..', '..', 'src', 'mcp', 'main.ts')],
    cwd: tmpdir(),
  });
  const client = new Client({ name: 'test-client', version: '1.0.0' });
  await client.connect(transport);
  try {
    const { tools } = await client.listTools();

    assert.deepEqual(tools.map((tool) => tool.name).toSorted(), ['search_comments', 'search_post_comments', 'search_posts']);
  } finally {
    await client.close();
  }
});
