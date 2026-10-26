// Serve the production build locally, without installing dependencies.
import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../dist/',import.meta.url));
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.wasm':'application/wasm','.css':'text/css; charset=utf-8','.ttf':'font/ttf','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.txt':'text/plain; charset=utf-8'};
const csp=JSON.parse(await readFile(new URL('../src-tauri/tauri.conf.json',import.meta.url),'utf8')).app.security.csp;
await stat(path.join(root,'index.html')).catch(()=>{console.error('Production build missing. Run pnpm install and pnpm build first.');process.exit(1);});
const server=http.createServer(async(req,res)=>{try{const requestPath=decodeURIComponent(new URL(req.url??'/','http://localhost').pathname);const target=path.resolve(root,'.'+(requestPath==='/'?'/index.html':requestPath));const relative=path.relative(root,target);if(relative.startsWith('..')||path.isAbsolute(relative)){res.writeHead(403);res.end();return;}const bytes=await readFile(target);res.writeHead(200,{'Content-Type':types[path.extname(target)]??'application/octet-stream','X-Content-Type-Options':'nosniff','Content-Security-Policy':csp});res.end(bytes);}catch{res.writeHead(404);res.end('Not found');}});
server.on('error',e=>{console.error(e.message);process.exitCode=1;});
server.listen(1440,'127.0.0.1',()=>console.log('Folio browser preview: http://127.0.0.1:1440\nPress Ctrl+C to stop. This is the browser preview, not the native desktop app.'));
