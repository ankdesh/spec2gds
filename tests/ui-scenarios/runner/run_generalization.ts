/** Repeated live inference evaluation; never route requests to canned fixtures. */
import { selectedEvaluationCases } from "./generalization_state.js";
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const args = process.argv.slice(2);
function option(name: string, fallback: string): string { const index=args.indexOf(name); return index<0 ? fallback : args[index+1] || fallback; }
const manifest=JSON.parse(readFileSync(join(root,"tests/evaluation/rtl/cases.json"),"utf8"));
const output=resolve(option("--output",join(root,"tests/ui-scenarios/results",`generalization-${Date.now()}`)));
mkdirSync(output,{recursive:true});
const runs: any[]=[];
if (!process.env.OPENAI_API_KEY) {
  writeFileSync(join(output,"summary.json"),JSON.stringify({status:"unverified",reason:"OPENAI_API_KEY unavailable; no live inference runs performed.",cases:manifest.cases.map((item:any)=>item.id)},null,2));
  throw new Error("OPENAI_API_KEY is required for repeated live-model evaluation.");
}
const repeats=Number(option("--repeats",String(manifest.live_repeats)));
if(!Number.isSafeInteger(repeats)||repeats<1) throw new Error("--repeats must be a positive integer.");
const selected=option("--case","");
const cases=selectedEvaluationCases<any>(manifest.cases,selected);
for(const item of cases) for(let repeat=0;repeat<repeats;repeat++) {
  const destination=join(output,`${item.id}-${repeat+1}`);
  const argv=["--import","tsx",join(root,"tests/ui-scenarios/runner/run_scenario.ts"),"--scenario","generalization","--live-model","--eval-case",item.id,"--output",destination];
  const benchmark=option("--benchmark-root",""); if(benchmark) argv.push("--benchmark-root",benchmark);
  const run=spawnSync(process.execPath,argv,{cwd:join(root,"tests/ui-scenarios"),stdio:"inherit",timeout:600000});
  runs.push({case:item.id,repeat:repeat+1,status:run.status===0?"passed":"failed",output:destination,error:run.error?.message});
  writeFileSync(join(output,"summary.json"),JSON.stringify({status:"completed",runs,document_quality:"requires rubric review; deterministic functional passes do not imply document quality"},null,2));
}
process.exitCode=runs.some(run=>run.status!=="passed")?1:0;
