/** Promotion evidence and production locks must be complete before application files change. */
import test from 'node:test';
import type {TestContext} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,cpSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
function fixture(t: TestContext, thirdParty = false) {
 const directory=mkdtempSync(join(tmpdir(),'release-adoption-'));t.after(()=>rmSync(directory,{recursive:true,force:true}));
 const application=join(directory,'application'),releaseDirectory=join(directory,'release'),verification=join(directory,'verification');
 for(const path of [join(application,'scripts'),releaseDirectory,verification,join(verification,'development'),join(application,'bundles/web'),join(application,'bundles/headless'),join(application,'bundles/replay')])mkdirSync(path,{recursive:true});
 const write=(path:string,value:unknown)=>writeFileSync(path,JSON.stringify(value,null,2)+'\n');
 cpSync(resolve('scripts/adopt-harness-release.mjs'),join(application,'scripts/adopt-harness-release.mjs'));
 const version='0.1.6-test.1',dependency='@ankdesh/dsh';
 const roots:Record<string,string>={[dependency]:version,...(thirdParty?{zod:'^4'}:{})};
 const release={releaseId:version,sourceCommit:'source',consumerCommit:'consumer',sourceDirty:false,consumerDirty:false,packages:[{name:dependency,version,integrity:'sha512-tested'}],profiles:{web:{roots},headless:{roots}}};
 write(join(releaseDirectory,'release-manifest.json'),release);
 const checksum=createHash('sha256').update(readFileSync(join(releaseDirectory,'release-manifest.json'))).digest('hex');
 const promotion={releaseId:version,sourceCommit:'source',releaseManifestSha256:checksum,verificationSha256:'',developmentLock:{} as Record<string,string>,productionLocks:{} as Record<string,Record<string,string>>};
 const records=[...['web','headless'].flatMap(name=>['install','graph','config','help','lock','ci','locked-graph','locked-config','assembly','assembled-config'].map(stage=>({name:name+'-'+stage,code:0}))),...['fast','integration','regression'].map(profile=>({name:'application-'+profile,code:0,consumerCommit:'consumer',sourceDirty:false}))];
 const evidence={releaseId:version,releaseManifestSha256:checksum,registryMode:'live-candidate',records};write(join(verification,'verification.json'),evidence);
 const lock={lockfileVersion:3,packages:{'':{dependencies:roots},['node_modules/'+dependency]:{version,integrity:'sha512-tested'},...(thirdParty?{'node_modules/zod':{version:'4.4.3',integrity:'sha512-zod'}}:{})}};
 for(const name of ['web','headless']){mkdirSync(join(verification,name));write(join(verification,name,'package.json'),{dependencies:roots});write(join(verification,name,'package-lock.json'),lock);}
 write(join(verification,'development/package.json'),{dependencies:roots});write(join(verification,'development/package-lock.json'),lock);
 promotion.developmentLock=Object.fromEntries(['package.json','package-lock.json'].map(filename=>[filename,createHash('sha256').update(readFileSync(join(verification,'development',filename))).digest('hex')]));
 promotion.verificationSha256=createHash('sha256').update(readFileSync(join(verification,'verification.json'))).digest('hex');
 for(const name of ['web','headless'])promotion.productionLocks[name]=Object.fromEntries(['package.json','package-lock.json'].map(filename=>[filename,createHash('sha256').update(readFileSync(join(verification,name,filename))).digest('hex')]));
 write(join(releaseDirectory,'promotion.json'),promotion);
 write(join(application,'harness.product.json'),{profiles:{web:{},headless:{}}});write(join(application,'harness.lock.json'),{status:'pending-publication'});
 for(const path of ['.','bundles/web','bundles/headless','bundles/replay'])write(join(application,path,'package.json'),{dependencies:{[dependency]:'old',...(thirdParty?{zod:'^4'}:{})}});
 const before=readFileSync(join(application,'package.json'),'utf8');
 const run=()=>spawnSync(process.execPath,[join(application,'scripts/adopt-harness-release.mjs'),releaseDirectory,verification],{encoding:'utf8'});
 return {application,releaseDirectory,verification,write,promotion,evidence,lock,before,run};
}
test('adoption rejects empty acceptance evidence before changing manifests',t=>{
 const f=fixture(t);f.write(join(f.verification,'verification.json'),{...f.evidence,records:[]});assert.notEqual(f.run().status,0);assert.equal(readFileSync(join(f.application,'package.json'),'utf8'),f.before);
});
test('adoption rejects an omitted production root',t=>{
 const f=fixture(t);f.write(join(f.verification,'web/package.json'),{dependencies:{}});const result=f.run();assert.notEqual(result.status,0);assert.match(result.stderr,/Production dependencies differ/);assert.equal(readFileSync(join(f.application,'package.json'),'utf8'),f.before);
});
test('adoption rejects a changed archive integrity in the production lock',t=>{
 const f=fixture(t);f.lock.packages['node_modules/@ankdesh/dsh'].integrity='sha512-other';f.write(join(f.verification,'web/package-lock.json'),f.lock);const result=f.run();assert.notEqual(result.status,0);assert.match(result.stderr,/tested archive/);assert.equal(readFileSync(join(f.application,'package.json'),'utf8'),f.before);
});
test('adoption rejects a promotion for a different source commit',t=>{
 const f=fixture(t);f.write(join(f.releaseDirectory,'promotion.json'),{...f.promotion,sourceCommit:'other'});assert.notEqual(f.run().status,0);assert.equal(readFileSync(join(f.application,'package.json'),'utf8'),f.before);
});
test('complete promotion evidence adopts exact production locks',t=>{
 const f=fixture(t);const result=f.run();assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(readFileSync(join(f.application,'harness.lock.json'),'utf8')).status,'promoted');assert.equal(readFileSync(join(f.application,'production/web/package-lock.json'),'utf8'),readFileSync(join(f.verification,'web/package-lock.json'),'utf8'));assert.equal(readFileSync(join(f.application,'package-lock.json'),'utf8'),readFileSync(join(f.verification,'development/package-lock.json'),'utf8'));
});
test('adoption retains third-party ranges while the production lock pins exact archive bytes',t=>{
 const f=fixture(t,true),result=f.run();assert.equal(result.status,0,result.stderr);const manifest=JSON.parse(readFileSync(join(f.application,'package.json'),'utf8'));assert.equal(manifest.dependencies.zod,'^4');const lock=JSON.parse(readFileSync(join(f.application,'production/web/package-lock.json'),'utf8'));assert.equal(lock.packages['node_modules/zod'].version,'4.4.3');
});
test('adoption rejects third-party lock changes even when the requested range is unchanged',t=>{
 const f=fixture(t,true);const lock=JSON.parse(readFileSync(join(f.verification,'web/package-lock.json'),'utf8'));lock.packages['node_modules/zod'].version='4.5.0';f.write(join(f.verification,'web/package-lock.json'),lock);const result=f.run();assert.notEqual(result.status,0);assert.match(result.stderr,/Verified production file checksum differs/);assert.equal(readFileSync(join(f.application,'package.json'),'utf8'),f.before);
});
test('adoption replaces a local candidate lock even when package versions already match',t=>{
 const f=fixture(t);f.write(join(f.application,'package.json'),{dependencies:{'@ankdesh/dsh':'0.1.6-test.1'}});const old=structuredClone(f.lock);old.packages['node_modules/@ankdesh/dsh'].integrity='sha512-local-candidate';f.write(join(f.application,'package-lock.json'),old);const result=f.run();assert.equal(result.status,0,result.stderr);assert.equal(readFileSync(join(f.application,'package-lock.json'),'utf8'),readFileSync(join(f.verification,'development/package-lock.json'),'utf8'));
});
