/** Assemble a product from installed packages and a verified release manifest. */
import {cpSync, readFileSync, existsSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {assembleProduct} from '@ankdesh/dsh-product-tools';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const output=process.argv[2]&&resolve(process.argv[2]);
const profile=process.argv[3]||'spec2gds-web';
const install=process.env.ASSISTANT_INSTALL_ROOT&&resolve(process.env.ASSISTANT_INSTALL_ROOT);
if(!output||!install)throw new Error('Usage: ASSISTANT_INSTALL_ROOT=LOCKED_PROFILE_INSTALL npm run package -- NEW_DIRECTORY [PROFILE]');
const lock=JSON.parse(readFileSync(resolve(root,'harness.lock.json'),'utf8'));
const recipe=JSON.parse(readFileSync(resolve(root,'harness.product.json'),'utf8'));
if(!Object.hasOwn(recipe.profiles,profile))throw new Error(`Unknown profile ${profile}`);
if(!existsSync(resolve(install,'release-manifest.json')))throw new Error('The tested release manifest is missing from the install root.');
assembleProduct({from:install,output,roots:['@ankdesh/dsh','@ankdesh/dsh-product-tools',...recipe.profiles[profile].bundles],
 releaseManifest:resolve(install,'release-manifest.json'),releaseManifestSha256:lock.releaseManifestSha256});
for(const entry of ['deployment','harness.lock.json'])cpSync(resolve(root,entry),resolve(output,entry),{recursive:true});
// A release contains only the selected production profile.
const {writeFileSync}=await import('node:fs');
recipe.profiles={[profile]:{...recipe.profiles[profile],localBundles:recipe.profiles[profile].bundles.map(name=>'../'+name)}};
recipe.defaultProfile=profile;
writeFileSync(resolve(output,'harness.product.json'),JSON.stringify(recipe,null,2)+'\n');
