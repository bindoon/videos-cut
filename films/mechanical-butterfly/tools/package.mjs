import {build} from 'esbuild';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]??path.join(root,'../../outputs/mechanical-butterfly/aurelia-interactive.html'));
const result=await build({entryPoints:[path.join(root,'main.js')],bundle:true,format:'esm',target:'es2022',minify:true,write:false,legalComments:'inline'});
const script=result.outputFiles[0].text.replace(/<\/script/gi,'<\\/script');
let html=await fs.readFile(path.join(root,'index.html'),'utf8');
html=html.replace('<html lang="zh-CN">','<html lang="zh-CN" data-interactive="true">')
  .replace(/<script type="importmap">.*?<\/script>/s,'')
  .replace('<script type="module" src="./main.js"></script>',()=>`<script type="module">${script}</script>`);
await fs.mkdir(path.dirname(output),{recursive:true});await fs.writeFile(output,html);
console.log(JSON.stringify({output,bytes:Buffer.byteLength(html),selfContained:true}));
