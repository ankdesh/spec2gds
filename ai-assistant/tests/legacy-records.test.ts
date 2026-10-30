import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {Context} from '@ankdesh/cordis';
import Persistence from '@ankdesh/dsh-session-persistence-jsonl';
import {SessionId} from '@ankdesh/dsh-session';

test('historical execution records remain readable without the retired execution packages',async()=>{
 const root=await mkdtemp(join(tmpdir(),'legacy-record-'));
 const id=SessionId('historical-execution');const directory=join(root,'_no-cwd',id);
 const event={seq:0,time:1001,type:'s-workflow/change',data:{kind:'s-workflow/change',version:1,operation:'complete',workflow:{runId:'old-run',revision:1,status:'completed',draft:{title:'Historical review'},receipt:{revision:'saved'}}}};
 const original=JSON.stringify({type:'session',version:3,id,createdAt:1000,isSeeded:false,delegationDepth:0})+'\n'+JSON.stringify(event)+'\n';
 await mkdir(directory,{recursive:true});const path=join(directory,'session.v3.jsonl');await writeFile(path,original);
 const ctx=new Context();
 try {
  await ctx.plugin(Persistence,{root,compression:'none'});
  const handle=await ctx.sessionPersistence.open(id,'read');
  try {const restored=await handle.read();assert.deepEqual(restored.events,[event]);}finally{await handle.close();}
  assert.equal(await readFile(path,'utf8'),original,'Reading must preserve the historical file bytes.');
 }finally{await ctx.fiber.dispose();await rm(root,{recursive:true,force:true});}
});
