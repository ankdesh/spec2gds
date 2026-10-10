/** Domain admission cannot restore legacy Spec write tools. HTTP behavior is covered by the real flow Loader suite. */
import assert from "node:assert/strict";
import test from "node:test";
import { registerDomainTools } from "../src/tools.js";
import { ProductState } from "../src/state.js";

for (const scope of ["document", "entity"] as const) for (const readOnly of [false, true]) test(`Spec ${scope} admission stays read-only with readOnly=${readOnly}`, () => {
  const state=new ProductState(":memory:");
  try {
    const tools=new Map<string,any>();
    const ctx={tools:{register(tool:any){tools.set(tool.name,tool);return()=>tools.delete(tool.name);}}};
    registerDomainTools(ctx,{domain:"spec",scope,documentId:"doc",sessionId:"source",entityKind:"component",entityId:"component"} as any,
      state,{} as any,undefined,undefined,undefined,true,{tool_schema:{type:"json"}} as any,undefined,undefined,readOnly);
    assert.deepEqual([...tools.keys()],["get_bound_context"]);
  } finally { state.close(); }
});
