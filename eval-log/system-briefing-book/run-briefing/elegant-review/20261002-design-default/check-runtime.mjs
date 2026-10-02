import {readFileSync,writeFileSync,mkdirSync,copyFileSync} from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {launchBrowser,findBrowser} from '../../../../../plugins/system-briefing-book/scripts/lib/browser-session.mjs';
const root = path.dirname(fileURLToPath(import.meta.url));
const book = JSON.parse(readFileSync(path.join(root, 'runtime-book.json'), 'utf8'));
const delivery = path.join(root,'runtime','delivery');
mkdirSync(delivery,{recursive:true});
const file = path.join(delivery,'打ち合わせ資料.html');
copyFileSync(book.out,file);
const browser = await launchBrowser(findBrowser());
const evidence=[];
try {
  for (const width of [1440,390]) {
    const page = await browser.newPage({width,height:1000});
    await page.goto(pathToFileURL(file).href+'#p-req');
    const result = await page.evaluate(`(async () => {
      const images=await Promise.all([...document.images].map(async img=>{try {await img.decode();return img.naturalWidth>0&&img.src.startsWith('data:');}catch{return false;}}));
      const s=getComputedStyle(document.body);
      return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,ink:s.color,background:s.backgroundColor,font:s.fontFamily,images,visible:[...document.querySelectorAll('main>.page')].filter(e=>getComputedStyle(e).display!=='none').map(e=>e.id)};
    })()`);
    writeFileSync(path.join(root,`runtime-${width}.png`),await page.screenshot());
    evidence.push(result);
    await page.close();
  }
} finally {await browser.close();}
writeFileSync(path.join(root,'runtime-browser.json'),JSON.stringify(evidence,null,2)+'\n');
if(evidence.some(x=>x.overflow||x.images.some(y=>!y)||x.ink!=='rgb(20, 35, 59)'))process.exitCode=1;
console.log(JSON.stringify(evidence.map(({images,...x})=>({...x,decodedImages:images.length}))));
