/** Simulated human receipt for tests of native execution after architecture review.
 * Full approval-card ordering is covered by isolated real-owner UI scenarios. */
import { join } from 'node:path';
import { ProductState } from '../../lib/state.js';
export function approveTimer(directory, sessionId, revision = 'sha256:test', reviewId = 'approved-timer') {
  const state = new ProductState(join(directory, 'assistant.sqlite3'));
  try {
    state.storeArchitecture({ reviewId, sessionId, callId: reviewId,
      status: 'pending', sourceRevision: revision, originalRequest: 'Add timer',
      plan: { components: [{ name: 'timer' }], designs: [], interfaces: [{ component: 'timer', ports: [], parameters: [], constant_context: "" }],
        open_questions: [], concrete_configuration: { implemented: false } } });
    state.decideArchitecture(reviewId, 'approved', 'Test human accepts this architecture.');
  } finally { state.close(); }
}
