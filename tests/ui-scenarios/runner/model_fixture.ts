/** Deterministic OpenAI-compatible provider using the real assistant transport. */
import { createServer } from "node:http";
import { once } from "node:events";

function content(message: any): string {
  return typeof message.content === "string" ? message.content
    : Array.isArray(message.content) ? message.content.map((part: any) => part.text ?? "").join("") : "";
}

export function parseToolOutputs(messages: any[]): any[] {
  const calls = new Map(messages.flatMap(message => (message.tool_calls || []).map((call: any) => [call.id, call.function.name])));
  return messages.filter(message => message.role === "tool").map(message => {
    const name = calls.get(message.tool_call_id) || "unknown tool";
    let result: any;
    try { result = JSON.parse(content(message)); }
    catch { throw new Error(`Malformed structured output from ${name} (${message.tool_call_id || "unknown call"}).`); }
    if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error(`Invalid structured output from ${name}.`);
    if (["prepare_circuit_proposal"].includes(String(name)) && !result.review && !result.error && !result.required_input
      && !(typeof result.proposal_id === "string" && ["ready", "applied", "rejected", "stale", "reconcile", "sent", "discarded"].includes(result.state))) {
      throw new Error(`Missing proposal outcome from ${name}.`);
    }
    return result;
  });
}

export function componentDescription(large = false): string {
  return "Combinational IRQ replicates clk & rst_n into eight bits.\nThere is no clocked state or reset sequence; inputs act as logical values."
    + (large ? "\nDetailed interface explanation. ".repeat(2400) + "\nLarge proposal complete." : "");
}

export async function modelFixture(documentId: string, options: { title?: string; largeProposal?: boolean; presentation?: boolean } = {}) {
  const requests: any[] = [];
  const failures: string[] = [];
  const fail = (response: any, error: unknown) => {
    const failure = String(error); failures.push(failure);
    response.writeHead(200, { "Content-Type": "text/event-stream" });
    response.end(`data: ${JSON.stringify({ id: "fixture-failure", object: "chat.completion.chunk", created: 1, model: "gpt-4o-mini", choices: [{ index: 0, delta: { role: "assistant", content: failure }, finish_reason: "stop" }] })}\n\ndata: [DONE]\n\n`);
  };
  const server = createServer(async (request, response) => {
    try {
      let raw = ""; for await (const chunk of request) raw += chunk;
      const body = JSON.parse(raw); requests.push(body);
      const messages: any[] = body.messages;
      const latestUser = messages.findLastIndex(message => message.role === "user");
      const turn = messages.slice(latestUser + 1);
      let outputs: any[];
      try { outputs = parseToolOutputs([...messages.slice(0, latestUser + 1).filter(message => message.role === "assistant"), ...turn]); }
      catch (error) {
        fail(response, error);
        return;
      }
      const userText = content(messages[latestUser]);
      let phase: any;
      try { const value=JSON.parse(userText); if(typeof value.phase === "string" && value.inputs) phase=value; } catch {}
      const phaseContext=phase?.inputs.authoring_context || phase?.inputs.context;
      const contextPages=phaseContext?.pages || outputs.filter(output=>output.authoritative_context).map(output=>output.authoritative_context);
      const context=phaseContext || contextPages.at(-1);
      const materialized:any={};
      for(const page of contextPages)for(const record of page.records || []){
        let node=materialized;
        for(let index=0;index<record.path.length-1;index++){const key=record.path[index];node=node[key]??=typeof record.path[index+1]==="number"?[]:{};}
        const key=record.path.at(-1);node[key]=record.offset===undefined || record.offset===0?record.value:String(node[key]||"")+record.value;
      }
      const component=(materialized.entities || []).map((item:any)=>item.entity).find((item:any)=>item.vlnv==="spec2gds.local:work:timer_core:1.0")
        || context?.available_references?.components?.find((item:any)=>item.vlnv==="spec2gds.local:work:timer_core:1.0");
      const toolNames=new Set(body.tools?.map((tool:any)=>tool.function.name));
      let name:string|undefined,args:any={};
      let text="Read-only analysis is complete. Flow acceptance does not confirm a saved change.";
      const composition = options.presentation && (phase?.inputs.request || userText).includes("entry Design");
      const width=component && !composition?16:8;
      const ports=[{name:"clk",direction:"in",range: null, description: "Port purpose"},{name:"rst_n",direction:"in",range: null, description: "Port purpose"},{name:"irq",direction:"out",range:`${width-1}:0`,description:"Replicated input conjunction"}];
      if(phase){
        if(toolNames.size!==1 || !toolNames.has("structured_output"))throw new Error("A flow phase must expose only structured_output.");
        name="structured_output";
        if(phase.phase.endsWith("architecture/draft"))args={title:`Timer architecture (${width} bits)`,components:[{name:"timer_core",purpose:"Replicate clk & rst_n"}],designs:composition?[{name:"irq_pipeline",purpose:"Connect two existing timer instances."}]:[],interfaces:[{component:"timer_core",ports, parameters: [], constant_context: "" }],clocks_resets:["Combinational inputs, without state."],decomposition_rationale:"One cohesive combinational leaf.",assumptions:[],open_questions:[],concrete_configuration:{width}};
        else if(phase.phase==="draft"){
          if(!component)throw new Error("The edit phase has no authoritative timer Component.");
          const oldPort=component.ports?.find((port:any)=>port.name==="irq");
          args={supported:true,unsupported_reason:null,base_source_revision_hash:context.source_revision_hash,title:"Refine timer",summary:"Set IRQ width to sixteen bits.",rationale:"Requested refinement.",assumptions:[],operations:[
            {operation_id:"port",type:"upsert_component_port",component:component.ref,port:{name:"irq",family:"wire",direction:"out",range:"15:0",...(oldPort?.description?{description:oldPort.description}:{})}},
            {operation_id:"section",type:"upsert_entity_section",owner:component.ref,section_type:"sv",type_version:1,payload:{content:"assign irq = {16{clk & rst_n}};"}}]};
          if(composition){
            const design={document_id:context.document_id,entity_kind:"design",entity_id:"local_pipeline"};
            args.operations=[{operation_id:"pipeline",type:"create_entity",kind:"design",name:"irq_pipeline",entity_id:"local_pipeline",entry_design:true,instances:[{name:"stage_a",component_vlnv:component.vlnv},{name:"stage_b",component_vlnv:component.vlnv}]},
              {operation_id:"pipeline_link",type:"upsert_connection",design,connection:{name:"irq_bit_zero",kind:"ad_hoc",port_endpoints:[{instance_name:"stage_a",port_name:"irq",slice:{lsb:0,width:1}},{instance_name:"stage_b",port_name:"clk"}]}},
              {operation_id:"pipeline_description",type:"set_entity_metadata",entity:design,display_name:"IRQ pipeline",description:"Two instances of IRQ logic form a combinational path. The first IRQ output bit drives the second logical input."},
              {operation_id:"component_label",type:"set_entity_metadata",entity:component.ref,display_name:"IRQ logic"}];
          }
        }else{
          const approved=context.architecture.interfaces[0].ports;
          const bounds=approved.find((port:any)=>port.name==="irq").range.split(":").map(Number);
          const approvedWidth=Math.abs(bounds[0]-bounds[1])+1;
          args={name:"timer_core",ports:approved,parameters:context.approved_component.parameters,description:componentDescription(options.largeProposal),narrative:"IRQ replicates the conjunction of the two scalar inputs.",systemverilog:`assign irq = {${approvedWidth}{clk & rst_n}};`};
        }
      }else if(toolNames.has("flow_create_spec_with_component") && !toolNames.has("get_bound_context")){
        name="flow_create_spec_with_component";args={title:options.title || "Iterative scenario",request:userText};
      }else if(!context && toolNames.has("get_bound_context"))name="get_bound_context";
      else if(context?.incomplete && toolNames.has("get_bound_context")){name="get_bound_context";args={cursor:context.next_cursor};}
      else if(outputs.some(output=>typeof output.execution_id==="string"))text="The flow was accepted. Inspect its progress and saved receipt.";
      else if(toolNames.has("flow_edit_spec") && component){name="flow_edit_spec";args={title:"Refine timer",request:userText};}
      else if(toolNames.has("flow_add_component")){name="flow_add_component";args={title:"Add timer",request:userText};}
      const delta = name ? { tool_calls: [{ index: 0, id: `fixture_${requests.length}`, type: "function", function: { name, arguments: JSON.stringify(args) } }] } : { content: text };
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      for (const [index, value] of [{ role: "assistant" }, delta, {}].entries()) {
        response.write(`data: ${JSON.stringify({ id: "fixture", object: "chat.completion.chunk", created: 1, model: "gpt-4o-mini", choices: [{ index: 0, delta: value, finish_reason: index === 2 ? name ? "tool_calls" : "stop" : null }] })}\n\n`);
      }
      response.end("data: [DONE]\n\n");
    } catch (error) { fail(response, error); }
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); if (!address || typeof address === "string") throw new Error("Fixture address missing");
  return { url: `http://127.0.0.1:${address.port}/v1`, requests, failures,
    close: () => new Promise<void>(resolve => { server.closeAllConnections(); server.close(() => resolve()); }) };
}
