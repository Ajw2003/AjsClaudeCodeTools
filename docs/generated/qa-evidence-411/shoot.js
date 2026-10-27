// Takes the pictures and the recording for the QA page of #411 from the pages make_demo.py built.
// Usage: NODE_PATH=/opt/node22/lib/node_modules node shoot.js <work dir> <out dir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [work, out] = process.argv.slice(2);
const page = (name) => 'file://' + path.join(work, 'pages', name);

async function openChanges(p) {
  await p.waitForTimeout(400);
  await p.click('[data-go="2"]');
  await p.waitForTimeout(600);  // the panel fades in; wait it out so the shot is not mid-fade
}

(async () => {
  const b = await chromium.launch();
  fs.mkdirSync(out, { recursive: true });

  // Before: the page aj got, built by the builder on main. In short, then Changes.
  for (const [w, h, tag] of [[390, 844, 'phone'], [1280, 900, 'desktop']]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto(page('old-builder.html'));
    await p.waitForTimeout(600);
    await p.screenshot({ path: path.join(out, `before-short-${tag}.png`) });
    await openChanges(p);
    await p.screenshot({ path: path.join(out, `before-changes-${tag}.png`) });
    await p.close();
  }

  // After: the same page with evidence, built by the new builder. Changes opens on the proof cards.
  for (const [w, h, tag] of [[390, 844, 'phone'], [1280, 900, 'desktop']]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto(page('new-builder.html'));
    await openChanges(p);
    await p.waitForTimeout(2500);  // let the clips play a little so frames show
    await p.screenshot({ path: path.join(out, `after-changes-${tag}.png`) });
    await p.screenshot({ path: path.join(out, `after-changes-${tag}-full.png`), fullPage: true });
    await p.close();
  }

  // The refusal the new builder gives for the page as sent, drawn as a terminal.
  const builds = JSON.parse(fs.readFileSync(path.join(work, 'builds.json'), 'utf8'));
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const html = `<body style="margin:0;background:#14120E;color:#DCD2BA;font:15px/1.5 ui-monospace,monospace;padding:20px">
    <div style="color:#9A9078">$ python3 make_page.py build ophan-as-sent.page.json (builder on main)</div>
    <div>${esc(builds['old builder, page as sent'][1].split('\n')[0].replace(work, '…'))}</div>
    <div style="color:#5FA288">exit ${builds['old builder, page as sent'][0]}: the page is built with no clip or picture</div><br>
    <div style="color:#9A9078">$ python3 make_page.py build ophan-as-sent.page.json (new builder)</div>
    <div style="color:#C4542E">${esc(builds['new builder, page as sent'][1])}</div>
    <div style="color:#C4542E">exit ${builds['new builder, page as sent'][0]}: refused</div></body>`;
  const t = await b.newPage({ viewport: { width: 900, height: 260 } });
  await t.setContent(html);
  await t.screenshot({ path: path.join(out, 'refusal.png') });
  await t.close();

  // A recording of the new page at phone width: open Changes, scroll through the proof cards with clips playing.
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, recordVideo: { dir: work, size: { width: 390, height: 844 } } });
  const r = await ctx.newPage();
  await r.goto(page('new-builder.html'));
  await openChanges(r);
  for (let y = 0; y <= 2400; y += 300) {
    await r.evaluate((yy) => window.scrollTo({ top: yy, behavior: 'smooth' }), y);
    await r.waitForTimeout(1200);
  }
  const vid = await r.video().path();
  await ctx.close();
  fs.copyFileSync(vid, path.join(work, 'walkthrough.webm'));
  await b.close();
  console.log('shots written to ' + out);
})();
