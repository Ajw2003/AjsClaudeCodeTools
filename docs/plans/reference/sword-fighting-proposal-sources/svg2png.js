const { chromium } = require('playwright'); const path=require('path');
(async()=>{ const b=await chromium.launch(); const p=await b.newPage({viewport:{width:960,height:560}});
for(const f of process.argv.slice(2)){ await p.goto('file://'+f); const el=await p.$('svg'); await el.screenshot({path:f.replace(/\.svg$/,'.png')}); console.log('ok',path.basename(f)); }
await b.close(); })();
