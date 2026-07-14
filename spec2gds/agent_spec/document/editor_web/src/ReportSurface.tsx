import React, { useEffect, useMemo, useState } from "react";
import { A2uiSurface, Column, createComponentImplementation, type ReactComponentImplementation } from "@a2ui/react/v0_9";
import { Catalog, MessageProcessor, type SurfaceModel } from "@a2ui/web_core/v0_9";
import { z } from "zod";
import reportCatalogDefinition from "../../../a2ui/report_catalog.json";

type Check = { check_id: string; severity: string; message: string; passed: boolean };
type Artifact = { artifact_id: string; summary: string; role: string; media_type: string };

const ReportSummary = createComponentImplementation(
  { name: "ReportSummary", schema: z.object({ outcome: z.string(), summary: z.string() }).strict() },
  ({ props }) => <section className={`report-summary ${props.outcome}`}><strong>{props.outcome}</strong><p>{props.summary}</p></section>
);
const CheckList = createComponentImplementation(
  { name: "CheckList", schema: z.object({ checks: z.array(z.object({ check_id: z.string(), severity: z.string(), message: z.string(), passed: z.boolean() })) }).strict() },
  ({ props }) => <section className="report-checks"><h3>Postconditions</h3>{props.checks.map((check) => <p key={check.check_id} className={check.passed ? "passed" : "failed"}>{check.passed ? "✓" : "!"} {check.message}</p>)}</section>
);
const ArtifactList = createComponentImplementation(
  { name: "ArtifactList", schema: z.object({ artifacts: z.array(z.object({ artifact_id: z.string(), summary: z.string(), role: z.string(), media_type: z.string() }).passthrough()) }).strict() },
  ({ props }) => <section className="report-artifacts"><h3>Artifacts</h3>{props.artifacts.length === 0 ? <p>No artifacts were accepted.</p> : props.artifacts.map((artifact) => <p key={artifact.artifact_id}><strong>{artifact.summary}</strong><small>{artifact.role} · {artifact.media_type}</small></p>)}</section>
);

const reportCatalog = new Catalog<ReactComponentImplementation>(reportCatalogDefinition.catalogId, [Column, ReportSummary, CheckList, ArtifactList]);

export function ReportSurface({ messages, surfaceId }: { messages: Record<string, unknown>[]; surfaceId: string }) {
  const processor = useMemo(() => new MessageProcessor([reportCatalog]), []);
  const [surface, setSurface] = useState<SurfaceModel<ReactComponentImplementation> | null>(null);

  useEffect(() => {
    try {
      processor.processMessages(messages as never);
      setSurface(processor.model.getSurface(surfaceId) ?? null);
    } catch {
      setSurface(null);
    }
  }, [messages, processor, surfaceId]);

  return surface ? <A2uiSurface surface={surface} /> : <p className="empty-note">The action report could not be rendered.</p>;
}
