/** Fixed service contract fixtures for deterministic transport tests. */
import { readFileSync } from 'node:fs';
export function serveIntegrationMetadata(request, response) {
  if (/^\/documents\/edit-access\/(acquire|renew)(\?|$)/.test(request.url || "")) {
    response.writeHead(200, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ mode: 'edit', context_id: 'fixture-edit-context', participant_id: 'fixture-participant', expires_at: Date.now()/1000+300 }));
    return true;
  }
  if (!request.url?.split('?')[0].endsWith('/assistant/integration-metadata')) return false;
  const domain = request.url.startsWith('/api/circuit-designer/v1/') ? 'circuit' : 'spec';
  response.writeHead(200, { 'Content-Type': 'application/json' });
  response.end(readFileSync(new URL(`../fixtures/${domain}-integration-metadata.json`, import.meta.url), 'utf8'));
  return true;
}
