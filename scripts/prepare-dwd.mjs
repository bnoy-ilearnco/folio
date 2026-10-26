// Pin and bundle the full Python runtime. No CDN, package download or system Python at runtime.
import {mkdir,copyFile,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=new URL('../',import.meta.url);
const target=new URL('public/dwd/pyodide/',root);
await mkdir(target,{recursive:true});
for(const name of ['pyodide.js','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json'])
  await copyFile(new URL('node_modules/pyodide/'+name,root),new URL(name,target));
const manifest=JSON.parse(await readFile(new URL('public/dwd/PROVENANCE.json',root),'utf8'));
const sources={};
await mkdir(new URL('public/dwd/converter/',root),{recursive:true});
for(const [name,sha] of Object.entries(manifest.files)){
  const bytes=await readFile(new URL('vendor/folio-dwd/'+name,root));
  if(createHash('sha256').update(bytes).digest('hex')!==sha)throw Error('Folio source hash mismatch: '+name);
  sources[name]=bytes.toString('utf8');
}
await writeFile(new URL('public/dwd/converter/sources.json',root),JSON.stringify(sources));
