import type { CircuitDocument } from "@spec2gds/circuit-core";
import type { LayoutOptions } from "./index";

export type LayoutWorkerRequest =
  | { type: "layout"; request_id: string; document: CircuitDocument; options?: LayoutOptions }
  | { type: "cancel"; request_id: string };

export type LayoutWorkerResponse =
  | { type: "progress"; request_id: string; phase: "placing" | "routing" | "complete"; progress: number }
  | { type: "result"; request_id: string; document: CircuitDocument; elapsed_ms: number }
  | { type: "cancelled"; request_id: string }
  | { type: "error"; request_id: string; message: string };
