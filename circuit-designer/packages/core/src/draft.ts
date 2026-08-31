import type {
  CircuitDocument,
  CircuitOperation,
  CircuitOperationBatch,
  Diagnostic,
} from "./types.generated";
import { applyOperations } from "./engine";
import { clone } from "./model";

interface DraftState {
  document: CircuitDocument;
  operations: CircuitOperation[];
}

function coalescingKey(operation: CircuitOperation): string | undefined {
  if (operation.type === "set_instance_geometry") return `${operation.type}:${operation.instance_id}`;
  if (operation.type === "set_terminal_placement") return `${operation.type}:${operation.terminal_key}`;
  if (operation.type === "set_net_route") return `${operation.type}:${operation.net_id}`;
  if (operation.type === "set_label_geometry") return `${operation.type}:${operation.element_key}`;
  if (operation.type === "set_layout_settings") return operation.type;
  if (operation.type === "update_cycle_edge") return `${operation.type}:${operation.edge.id}`;
  if (operation.type === "set_clock_domain") return `${operation.type}:${operation.domain.id}`;
  if (operation.type === "set_subject_clock_domain") return `${operation.type}:${operation.subject_key}`;
  return undefined;
}

/** Private operation-based editing session. Nothing is persisted until toBatch() is committed. */
export class CircuitDraft {
  readonly baseRevision: string;
  readonly baseDocument: CircuitDocument;
  private current: DraftState;
  private undoStack: DraftState[] = [];
  private redoStack: DraftState[] = [];

  constructor(document: CircuitDocument, revision: string) {
    this.baseDocument = clone(document);
    this.baseRevision = revision;
    this.current = { document: clone(document), operations: [] };
  }

  get document(): CircuitDocument { return clone(this.current.document); }
  get operations(): CircuitOperation[] { return clone(this.current.operations); }
  get canUndo(): boolean { return this.undoStack.length > 0; }
  get canRedo(): boolean { return this.redoStack.length > 0; }
  get dirty(): boolean { return this.current.operations.length > 0; }

  apply(operation: CircuitOperation): Diagnostic[] {
    return this.applyBatch([operation]);
  }

  /** Apply a user-visible compound command atomically and record one undo step. */
  applyBatch(batch: CircuitOperation[]): Diagnostic[] {
    if (!batch.length) return [];
    const result = applyOperations(this.current.document, batch);
    if (!result.candidate) return result.diagnostics;
    this.undoStack.push(clone(this.current));
    this.redoStack = [];
    const operations = [...this.current.operations];
    for (const operation of batch) {
      const key = coalescingKey(operation);
      const priorIndex = key ? operations.findIndex((item) => coalescingKey(item) === key) : -1;
      if (priorIndex >= 0) operations[priorIndex] = clone(operation);
      else operations.push(clone(operation));
    }
    this.current = { document: result.candidate, operations };
    return result.diagnostics;
  }

  undo(): CircuitDocument {
    const previous = this.undoStack.pop();
    if (!previous) return this.document;
    this.redoStack.push(clone(this.current));
    this.current = previous;
    return this.document;
  }

  redo(): CircuitDocument {
    const next = this.redoStack.pop();
    if (!next) return this.document;
    this.undoStack.push(clone(this.current));
    this.current = next;
    return this.document;
  }

  cancel(): CircuitDocument {
    this.current = { document: clone(this.baseDocument), operations: [] };
    this.undoStack = [];
    this.redoStack = [];
    return this.document;
  }

  toBatch(requestId: string): CircuitOperationBatch {
    if (!this.current.operations.length) throw new Error("The draft contains no changes.");
    return {
      request_id: requestId,
      expected_revision: this.baseRevision,
      operations: clone(this.current.operations) as CircuitOperationBatch["operations"],
    };
  }
}
