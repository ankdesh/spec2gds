/** Adopt a promoted release and the clean consumer locks produced by its verification. */
import {readFileSync,writeFileSync,cpSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const [releaseArg,verificationArg]=process.argv.slice(2);
if(!releaseArg||!verificationArg)throw new Error('Usage: node scripts/adopt-harness-release.mjs PROMOTED_RELEASE_DIRECTORY VERIFIED_CONSUMER_DIRECTORY');
const directory=resolve(releaseArg),verification=resolve(verificationArg);
const bytes=readFileSync(join(directory,'release-manifest.json'));
const checksum=createHash('sha256').update(bytes).digest('hex');
const release=JSON.parse(bytes),promotion=JSON.parse(readFileSync(join(directory,'promotion.json'),'utf8'));
const evidenceBytes=readFileSync(join(verification,'verification.json'));
const evidence=JSON.parse(evidenceBytes);
if(release.sourceDirty||release.consumerDirty||!release.consumerCommit||release.measurementOnly||promotion.sourceCommit!==release.sourceCommit||promotion.releaseId!==release.releaseId||promotion.releaseManifestSha256!==checksum||promotion.verificationSha256!==createHash('sha256').update(evidenceBytes).digest('hex')||evidence.releaseId!==release.releaseId||evidence.registryMode!=='live-candidate'||evidence.releaseManifestSha256!==checksum||!Array.isArray(evidence.records)||!evidence.records.length||evidence.records.some(r=>r.code!==0))throw new Error('The release is not promoted with matching successful verification.');
const recipe=JSON.parse(readFileSync(join(root,'harness.product.json'),'utf8'));
const versions=new Map(release.packages.map(p=>[p.name,p.version]));
const equalDependencies=(a,b)=>JSON.stringify(Object.entries(a||{}).sort())===JSON.stringify(Object.entries(b||{}).sort());
function validateHarnessLocks(lock,label,allowLocalBundles){
 for(const [path,node]of Object.entries(lock.packages||{})){
  const packageName=path.split('node_modules/').at(-1),owned=packageName.startsWith('@ankdesh/');
  if((owned||!allowLocalBundles)&&(node.link||node.resolved?.startsWith('file:')))throw new Error(`${label} lock contains a source link: ${path}`);
  if(owned){const expected=release.packages.find(p=>p.name===packageName);if(!expected||node.version!==expected.version||node.integrity!==expected.integrity)throw new Error(`${label} lock differs from the tested archive: ${packageName}`);}
 }
}
for(const stage of ['application-fast','application-integration','application-regression'])if(!evidence.records.some(r=>r.name===stage&&r.code===0&&!r.sourceDirty&&r.consumerCommit===release.consumerCommit))throw new Error(`Missing consumer acceptance evidence: ${stage}`);
// Validate every input before changing an application lock or manifest.
for(const name of Object.keys(recipe.profiles)){
 if(!release.profiles?.[name]?.roots)throw new Error(`Release does not contain ${name}`);
 for(const stage of ['install','graph','config','help','lock','ci','locked-graph','locked-config','assembly','assembled-config'])if(!evidence.records.some(r=>r.name===name+'-'+stage&&r.code===0))throw new Error(`Missing verification: ${name}-${stage}`);
 if(release.profiles[name].packages?.includes('@ankdesh/ankdesh-web-runtime')&&!evidence.records.some(r=>r.name===name+'-web-start'&&r.code===0))throw new Error(`Missing verification: ${name}-web-start`);
 for(const filename of ['package.json','package-lock.json']) {
 const file=join(verification,name,filename);if(!existsSync(file))throw new Error(`Missing verified production file: ${file}`);
 const fileBytes=readFileSync(file),manifest=JSON.parse(fileBytes);
 const roots=release.profiles[name].roots;
 if(filename==='package.json'&&!equalDependencies(manifest.dependencies,roots))throw new Error(`Production dependencies differ for ${name}`);
 if(filename==='package-lock.json'){
  if(manifest.lockfileVersion!==3||!equalDependencies(manifest.packages?.['']?.dependencies,roots))throw new Error(`Production lock roots differ for ${name}`);
  validateHarnessLocks(manifest,'Production',false);
  for(const [packageName,version]of Object.entries(roots)){
   const node=manifest.packages['node_modules/'+packageName];
   if(!node||(packageName.startsWith('@ankdesh/')?node.version!==version:!node.integrity))throw new Error(`Production lock omits ${packageName}`);
  }
 }
 if(promotion.productionLocks?.[name]?.[filename]!==createHash('sha256').update(fileBytes).digest('hex'))throw new Error(`Verified production file checksum differs: ${name}/${filename}`);
 }
}
const updates=[];
for(const path of ['.','bundles/web','bundles/headless','bundles/replay']) {
 const file=join(root,path,'package.json'),manifest=JSON.parse(readFileSync(file,'utf8'));
 for(const section of ['dependencies','devDependencies'])for(const name of Object.keys(manifest[section]||{}))if(name.startsWith('@ankdesh/')){
  if(!versions.has(name))throw new Error(`Release omits declared application package ${name}`);
  manifest[section][name]=versions.get(name);
 }
 updates.push({file,manifest});
}
const developmentFiles={};
for(const filename of ['package.json','package-lock.json']){
 const data=readFileSync(join(verification,'development',filename));
 if(promotion.developmentLock?.[filename]!==createHash('sha256').update(data).digest('hex'))throw new Error(`Verified development file checksum differs: ${filename}`);
 developmentFiles[filename]=data;
}
const developmentManifest=JSON.parse(developmentFiles['package.json']);
const developmentLock=JSON.parse(developmentFiles['package-lock.json']);
const expected=updates[0].manifest;
for(const section of ['dependencies','devDependencies'])if(!equalDependencies(developmentManifest[section],expected[section])||!equalDependencies(developmentLock.packages?.['']?.[section],expected[section]))throw new Error('The verified development lock does not match this application. Verify its current dependency declarations before adoption.');
if(developmentLock.lockfileVersion!==3||JSON.stringify(developmentManifest.workspaces||[])!==JSON.stringify(expected.workspaces||[]))throw new Error('The verified development workspace lock does not match this application.');
validateHarnessLocks(developmentLock,'Development',true);
for(const {file,manifest}of updates)writeFileSync(file,JSON.stringify(manifest,null,2)+'\n');
writeFileSync(join(root,'package-lock.json'),developmentFiles['package-lock.json']);
for(const name of Object.keys(recipe.profiles)) {
 const destination=join(root,'production',name);mkdirSync(destination,{recursive:true});
 for(const file of ['package.json','package-lock.json'])cpSync(join(verification,name,file),join(destination,file));
}
mkdirSync(join(root,'releases'),{recursive:true});writeFileSync(join(root,'releases/harness-release-manifest.json'),bytes);
const lock=JSON.parse(readFileSync(join(root,'harness.lock.json'),'utf8'));
Object.assign(lock,{releaseId:release.releaseId,commit:release.sourceCommit,releaseManifestSha256:checksum,status:'promoted'});
writeFileSync(join(root,'harness.lock.json'),JSON.stringify(lock,null,2)+'\n');
console.log(`Adopted ${release.releaseId} and its tested locks. Run npm ci and the application checks before committing the dependency update.`);
