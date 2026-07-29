import { DatabaseSync } from "node:sqlite";
import {
  MemoryCircuitDesignerBackend,
  type CircuitRepositoryState,
  type MemoryBackendOptions,
} from "@spec2gds/circuit-client-local";

/**
 * SQLite-backed authoritative snapshot repository. Domain operations remain in
 * the shared memory backend; every accepted mutation persists the full portable
 * document in one SQLite transaction.
 */
export class SqliteCircuitDesignerBackend extends MemoryCircuitDesignerBackend {
  private constructor(private readonly database: DatabaseSync, options: MemoryBackendOptions) {
    super(options);
  }

  static open(path: string, options: MemoryBackendOptions = {}): SqliteCircuitDesignerBackend {
    const database = new DatabaseSync(path);
    database.exec(`
      PRAGMA journal_mode = WAL;
      CREATE TABLE IF NOT EXISTS circuit_state (
        document_id TEXT PRIMARY KEY,
        state_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    `);
    const backend = new SqliteCircuitDesignerBackend(database, options);
    const rows = database.prepare(
      "SELECT state_json FROM circuit_state ORDER BY document_id",
    ).all() as Array<{ state_json: string }>;
    for (const row of rows) {
      backend.insertState(JSON.parse(row.state_json) as CircuitRepositoryState);
    }
    return backend;
  }

  close(): void {
    this.database.close();
  }

  protected override async afterMutation(documentId: string): Promise<void> {
    const state = this.repositoryState(documentId);
    this.database.prepare(`
      INSERT INTO circuit_state (document_id, state_json, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(document_id) DO UPDATE SET
        state_json = excluded.state_json,
        updated_at = excluded.updated_at
    `).run(
      documentId,
      JSON.stringify(state),
      new Date().toISOString(),
    );
  }
}
