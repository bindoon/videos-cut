import {build} from 'esbuild';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]);
const result=await build({entryPoints:[path.join(root,'main.js')],bundle:true,format:'esm',target:'es2022',minify:true,write:false,legalComments:'inline'});
let html=await fs.readFile(path.join(root,'index.html'),'utf8');
let css=await fs.readFile(path.join(root,'fonts/fonts.css'),'utf8');
for(let i=0;i<4;i++){
 const name=`noto-sc-${i}.woff2`,base64=(await fs.readFile(path.join(root,'fonts',name))).toString('base64');
 css=css.replace(`./${name}`,`data:font/woff2;base64,${base64}`);
}
html=html.replace('<html lang="zh-CN">','<html lang="zh-CN" data-interactive="true">')
 .replace('<link rel="stylesheet" href="./fonts/fonts.css">',()=>`<style>${css}</style>`)
 .replace(/<script type="importmap">.*?<\/script>/s,'')
 .replace('<script type="module" src="./main.js"></script>',()=>`<script type="module">${result.outputFiles[0].text.replace(/<\/script/gi,'<\\/script')}</script>`);
await fs.writeFile(output,html);
await fs.copyFile(path.join(root,'fonts/OFL.txt'),path.join(path.dirname(output),'FONT-LICENSE.txt'));
console.log(JSON.stringify({output,bytes:Buffer.byteLength(html),selfContained:true}));
