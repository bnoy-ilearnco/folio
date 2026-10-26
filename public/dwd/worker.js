/* Folio offline reader, isolated from the editor and native IPC. */
let engine;
async function ready(){
  if(!engine)engine=(async()=>{
    importScripts('./pyodide/pyodide.js');
    const py=await loadPyodide({indexURL:new URL('./pyodide/',self.location.href).href});
    const response=await fetch('./converter/sources.json');
    if(!response.ok)throw Error('The bundled DavkaWriter reader is missing.');
    const sources=await response.json();
    py.FS.mkdirTree('/folio');
    for(const [name,source] of Object.entries(sources))py.FS.writeFile('/folio/'+name,source);
    py.runPython('import sys\nsys.path.insert(0, "/folio")\nimport dwd2docx\nimport json');
    return py;
  })();
  return engine;
}
self.onmessage=async({data})=>{
  let input,result;
  try{
    const py=await ready();
    input=py.toPy(data.bytes);py.globals.set('_folio_input',input);
    result=py.runPython('_folio_result = dwd2docx.convert_bytes(bytes(_folio_input), diagnostics=True)\n_folio_result[0]');
    const bytes=new Uint8Array(result.toJs());
    const diagnostics=JSON.parse(py.runPython('json.dumps(_folio_result[4])'));
    if(bytes.length>30*1024*1024)throw Error('The converted document exceeds the 30 MB import limit.');
    self.postMessage({bytes,diagnostics},[bytes.buffer]);
  }catch(error){
    // Do not expose internal paths or the document's text in notices/logging.
    self.postMessage({error:'This file could not be read as a DavkaWriter document. It may be damaged or use an unsupported format.'});
  }finally{
    result?.destroy();input?.destroy();
    if(engine){const py=await engine.catch(()=>null);if(py)py.runPython('globals().pop("_folio_input", None)\nglobals().pop("_folio_result", None)\nimport gc\ngc.collect()\nNone');}
  }
};
