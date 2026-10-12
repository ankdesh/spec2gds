/** Removed Spec results cannot invoke browser callbacks or show a proposal save card. */
import assert from "node:assert/strict";
import test from "node:test";
import vm from "node:vm";
import { readFileSync } from "node:fs";
function fixture() {
  let definition:any, tracker:any, tail:any;
  vm.runInNewContext(readFileSync(new URL("../client/index.js",import.meta.url),"utf8"),{
    window:{__ModuleLoader__:{load(value:any){definition=value;}}},URL,URLSearchParams,
    location:{pathname:"/",search:"",hash:""},document:{title:"",createElement:()=>({dataset:{}}),head:{appendChild(){}}},queueMicrotask(){},
  });
  definition.factory(()=>({createElement:(type:any,props:any)=>({type,props})})).apply({uiSession:{registerNewSessionHandler(){}},
    uiConversation:{events:{register(value:any){tracker=value;}}},sessions:{},workspaces:{},
    slots:{inject(_name:string,callback:any){callback();},register(options:any,component:any){if(options.name==="conversation.chat.turnTail")tail={options,component};}}});
  return {tracker,tail};
}
for (const name of ["prepare_spec_document_creation","prepare_architecture_review","prepare_spec_proposal"]) test(`browser ignores removed ${name} result`,()=>{
  const {tracker,tail}=fixture(); let state=tracker.start({}, {event:{type:"turn/start",data:{turn:1}}});
  state=tracker.update({state},{event:{type:"tool/call",data:{callId:"old",name}}});
  state=tracker.update({state},{event:{type:"tool/result",seq:3,data:{message:{source:{callId:"old"},content:[{content:[{type:"text",text:JSON.stringify({source_creation:{requestId:"old"},architecture_review:{reviewId:"old"},review:{domain:"spec",state:"ready"}})}]}]}}}});
  const location=tracker.buildLocationData({state},"turn",null);
  const selected=tail.options.select({seq:4,turn:{data:{get:()=>location.value}}});
  if(name === "prepare_spec_proposal") assert.equal(selected?.review?.state,"ready");
  else assert.equal(selected,null);
});
