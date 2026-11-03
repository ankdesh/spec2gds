/** Assemble a product from installed packages and a verified release manifest. */
import {cpSync, readFileSync, existsSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {assembleProduct} from '@ankdesh/ankdesh-product-tools';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const output=process.argv[2]&&resolve(process.argv[2]);
const profile=process.argv[3]||'spec2gds-web';
const install=process.env.ASSISTANT_INSTALL_ROOT&&resolve(process.env.ASSISTANT_INSTALL_ROOT);
if(!output||!install)throw new Error('Usage: ASSISTANT_INSTALL_ROOT=LOCKED_PROFILE_INSTALL npm run package -- NEW_DIRECTORY [PROFILE]');
const lock=JSON.parse(readFileSync(resolve(root,'harness.lock.json'),'utf8'));
const recipe=JSON.parse(readFileSync(resolve(root,'harness.product.json'),'utf8'));
if(!Object.hasOwn(recipe.profiles,profile))throw new Error(`Unknown profile ${profile}`);
if(!existsSync(resolve(install,'release-manifest.json')))throw new Error('The tested release manifest is missing from the install root.');
assembleProduct({from:install,output,roots:['@ankdesh/dsh','@ankdesh/ankdesh-product-tools',...recipe.profiles[profile].bundles],
 releaseManifest:resolve(install,'release-manifest.json'),releaseManifestSha256:lock.releaseManifestSha256});
for(const entry of ['deployment','harness.lock.json'])cpSync(resolve(root,entry),resolve(output,entry),{recursive:true});
// A release contains only the selected production profile.
const {writeFileSync}=await import('node:fs');
recipe.profiles={[profile]:{...recipe.profiles[profile],localBundles:recipe.profiles[profile].bundles.map(name=>'../'+name)}};
recipe.defaultProfile=profile;
writeFileSync(resolve(output,'harness.product.json'),JSON.stringify(recipe,null,2)+'\n');

// Ship the shared resolver and defaults. Releases do not require a repository checkout.
cpSync(resolve(root,'../runtime/service-config.cjs'),resolve(output,'runtime/service-config.cjs'),{recursive:true});
cpSync(resolve(root,'../runtime/service-config.mjs'),resolve(output,'runtime/service-config.mjs'),{recursive:true});
cpSync(resolve(root,'../runtime/src/spec2gds_runtime/service-defaults.json'),resolve(output,'runtime/src/spec2gds_runtime/service-defaults.json'),{recursive:true});
cpSync(resolve(root,'../config/services.json'),resolve(output,'config/services.json'),{recursive:true});
cpSync(resolve(root,'scripts/service-launch.mjs'),resolve(output,'scripts/service-launch.mjs'),{recursive:true});
// The release launcher keeps the repository-relative import layout.
const launcher=readFileSync(resolve(output,'scripts/service-launch.mjs'),'utf8').replace('../../runtime/service-config.mjs','../runtime/service-config.mjs');
writeFileSync(resolve(output,'scripts/service-launch.mjs'),launcher);
