// Build first with `pnpm tauri bundle --bundles nsis`, then package a single
// shareable installer. This verifies packaging inputs without executing setup.
import {readFile,copyFile,stat,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=new URL('../',import.meta.url);
const {version}=JSON.parse(await readFile(new URL('package.json',root),'utf8'));
const config=JSON.parse(await readFile(new URL('src-tauri/tauri.conf.json',root),'utf8'));
if(config.bundle.windows?.webviewInstallMode?.type!=='offlineInstaller')throw Error('Offline WebView2 installation must be enabled.');
const script=await readFile(new URL('src-tauri/target/release/nsis/x64/installer.nsi',root),'utf8');
if(!script.includes('!define INSTALLWEBVIEW2MODE "offlineInstaller"'))throw Error('NSIS did not embed offline WebView2.');
for(const file of ['library.sqlite','LIBRARY-NOTICES.txt'])if(!script.includes(`resources\\${file}`))throw Error('Missing bundled library resource: '+file);
for(const file of ['dist/dwd/worker.js','dist/dwd/converter/sources.json','dist/dwd/pyodide/pyodide.asm.wasm','dist/dwd/pyodide/python_stdlib.zip','dist/fonts/hebrew/NotoRashiHebrew-Regular.ttf','dist/fonts/hebrew/NotoRashiHebrew-Bold.ttf'])await stat(new URL(file,root));
const source=new URL(`src-tauri/target/release/bundle/nsis/Folio_${version}_x64-setup.exe`,root);
const name=`Folio-${version}-Windows-x64-Offline-Setup.exe`;
const output=new URL('../'+name,root);
await copyFile(source,output);
const bytes=await readFile(output);if(bytes[0]!==0x4d||bytes[1]!==0x5a)throw Error('Invalid Windows installer.');
const sha256=createHash('sha256').update(bytes).digest('hex');
await writeFile(new URL('../'+name+'.sha256',root),`${sha256}  ${name}\n`);
await writeFile(new URL('../'+name+'.json',root),JSON.stringify({version,file:name,bytes:bytes.length,sha256,platform:'Windows x64',single_file:true,webview2:'embedded offline installer',included:['Folio application','offline Tanakh, Babylonian Talmud and Rashi library','Hebrew fonts including Noto Rashi Hebrew','offline DWD import runtime','license notices','WebView2 offline prerequisite'],signing:'UNSIGNED',verification:'Tauri NSIS build succeeded; offline prerequisite and resource packaging inputs verified. This package has not been installed on a clean machine. Windows Application Control blocked the previous rebuilt unsigned installer.'},null,2)+'\n');
console.log(`${name}: ${bytes.length.toLocaleString()} bytes\nSHA-256: ${sha256}\nShare the EXE alone. Signature: UNSIGNED.`);
