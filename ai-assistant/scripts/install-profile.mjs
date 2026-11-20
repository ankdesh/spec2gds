/** Create one production install root from its committed lock. */
import {cpSync, existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {readHarnessRelease, verifyHarnessArchives, localizeHarnessLock} from './harness-archives.mjs';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const profile=process.argv[2]||'spec2gds-web';
const output=process.argv[3]&&resolve(process.argv[3]);
const recipe=JSON.parse(readFileSync(resolve(root,'harness.product.json'),'utf8'));
if(!output||!Object.hasOwn(recipe.profiles,profile))throw new Error('Usage: npm run install:profile -- spec2gds-web|spec2gds-headless NEW_DIRECTORY');
if(existsSync(output))throw new Error(`Output already exists: ${output}`);
const source=resolve(root,'production',profile);
if(!existsSync(resolve(source,'package-lock.json')))throw new Error('The production lock is missing. Adopt a tested package release before installation.');
const lock=JSON.parse(readFileSync(resolve(root,'harness.lock.json'),'utf8'));
if(lock.status!=='promoted'||!lock.releaseManifestSha256)throw new Error('Adopt a promoted Harness release before production installation.');
const release=readHarnessRelease(root);
verifyHarnessArchives(release,resolve(root,'vendor/harness'));
const installLock=localizeHarnessLock(JSON.parse(readFileSync(resolve(source,'package-lock.json'),'utf8')),release);
mkdirSync(output,{recursive:true});
cpSync(resolve(source,'package.json'),resolve(output,'package.json'));
writeFileSync(resolve(output,'package-lock.json'),JSON.stringify(installLock,null,2)+'\n');
cpSync(resolve(root,'vendor/harness'),resolve(output,'vendor/harness'),{recursive:true});
const result=spawnSync('npm',['ci','--omit=dev','--no-audit','--no-fund'],{cwd:output,env:process.env,stdio:'inherit'});
if(result.error)throw result.error;
if(result.status!==0){process.exitCode=result.status||1;}else{
 const {globSync}=await import('node:fs');
 const profileConfig=recipe.profiles[profile];
 for(const local of profileConfig.localBundles){
  const bundle=resolve(root,local),manifest=JSON.parse(readFileSync(resolve(bundle,'package.json'),'utf8'));
  const target=resolve(output,'node_modules',manifest.name);mkdirSync(target,{recursive:true});
  for(const pattern of manifest.files||[])for(const file of globSync(pattern,{cwd:bundle}))cpSync(resolve(bundle,file),resolve(target,file),{recursive:true});
  cpSync(resolve(bundle,'package.json'),resolve(target,'package.json'));
 }
 cpSync(resolve(root,'releases/harness-release-manifest.json'),resolve(output,'release-manifest.json'));
}
