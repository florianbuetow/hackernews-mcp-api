/** Serve the Hacker News search tools over stdio, for MCP clients such as Claude Code. */

import { join } from 'node:path';

import { serveStdio } from '@modelcontextprotocol/server/stdio';

import { loadConfig } from './config.ts';
import { createServer } from './server.ts';

const config = loadConfig(join(import.meta.dirname, '..', '..', 'config', 'search.toml'));

serveStdio(() => createServer(config, fetch), {
  onerror: (error) => {
    console.error(error);
    process.exit(1);
  },
});
