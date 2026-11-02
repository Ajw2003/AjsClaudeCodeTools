const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const root = __dirname;
const srv = http.createServer((q, r) => {
  const p = path.join(root, decodeURIComponent(q.url.split('?')[0]));
  fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); return r.end(); }
    r.writeHead(200, {'Content-Type': p.endsWith('.js') ? 'text/javascript' : 'text/html'}); r.end(d); });
}).listen(8765);
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const pg = await b.newPage({ viewport: { width: 1280, height: 720 } });
  pg.on('console', m => console.log('console:', m.text()));
  pg.on('pageerror', e => console.log('pageerror:', e.message));
  const shots = process.argv.slice(2);
  for (const s of shots) {
    const [shot, extra] = s.split('+');
    await pg.goto(`http://localhost:8765/scene.html?shot=${shot}${extra ? '&' + extra : ''}`);
    await pg.waitForFunction('window.__done === true', null, { timeout: 60000 });
    const out = path.join(root, 'out', s.replace(/[+=&]/g, '-') + '.png');
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await pg.locator('#wrap').screenshot({ path: out });
    console.log('wrote', out);
  }
  await b.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
