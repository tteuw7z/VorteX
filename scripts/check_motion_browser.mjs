// Test-only Chromium DevTools driver. No runtime JS is shipped in the UI.
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const output = resolve(process.argv[2] || 'motion-browser-evidence');
const work = await mkdtemp(join(tmpdir(), 'vx-browser-'));
let browser, ws;
let sequence = 0;
const pending = new Map();
const events = [];
let session;
function request(method, params = {}, target = session) {
  const id = ++sequence;
  return new Promise((ok, fail) => {
    const timeout = setTimeout(() => {
      pending.delete(id);
      fail(new Error('CDP timeout: ' + method));
    }, 10000);
    pending.set(id, {ok, fail, timeout});
    ws.send(JSON.stringify({id, method, params, ...(target ? {sessionId: target} : {})}));
  });
}
async function evaluate(expression) {
  const response = await request('Runtime.evaluate', {expression, returnByValue: true});
  if (response.exceptionDetails) throw new Error('Browser evaluation failed');
  return response.result.value;
}
async function waitFor(fn, label) {
  for (let i = 0; i < 80; i++) {
    try { if (await fn()) return; } catch {}
    await delay(50);
  }
  throw new Error('Timed out: ' + label);
}
async function navigate(name, width, height, reduced = false) {
  await request('Emulation.setDeviceMetricsOverride', {
    width, height, deviceScaleFactor: 1, mobile: width < 600,
  });
  await request('Emulation.setTouchEmulationEnabled', {enabled: width < 600, maxTouchPoints: 1});
  await request('Emulation.setEmulatedMedia', {
    features: [{name: 'prefers-reduced-motion', value: reduced ? 'reduce' : 'no-preference'}],
  });
  const url = pathToFileURL(join(work, name, 'index.html')).href;
  await request('Page.navigate', {url});
  await waitFor(() => evaluate('document.readyState === "complete" && location.href === ' + JSON.stringify(url)), 'navigation');
  assert.equal(await evaluate('getComputedStyle(document.body).backgroundColor'), 'rgb(13, 11, 20)', 'CSP must allow exact CSS');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, 'horizontal overflow');
  assert.equal(await evaluate('document.querySelectorAll("script,form").length'), 0);
}
async function center(selector) {
  return evaluate('(()=>{const n=document.querySelector(' + JSON.stringify(selector) +
    ');n.scrollIntoView({block:"center"});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()');
}
async function click(selector, touch = false) {
  const point = await center(selector);
  if (touch) {
    await request('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[point]});
    await request('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
  } else {
    await request('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...point});
    await request('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...point});
  }
}
async function key(key, code, windowsVirtualKeyCode) {
  const text = key === 'Enter' ? '\r' : key === ' ' ? ' ' : '';
  await request('Input.dispatchKeyEvent', {type:text ? 'keyDown' : 'rawKeyDown',key,code,
    windowsVirtualKeyCode, ...(text ? {text,unmodifiedText:text} : {})});
  await request('Input.dispatchKeyEvent', {type:'keyUp',key,code,windowsVirtualKeyCode});
}
async function screenshot(name) {
  const result = await request('Page.captureScreenshot', {format:'png',captureBeyondViewport:false});
  await writeFile(join(output, name + '.png'), Buffer.from(result.data, 'base64'));
}
try {
  await mkdir(output, {recursive:false});
  execFileSync(process.env.PYTHON || 'python', ['-c',
    'from pathlib import Path; from vortex.interface import write_preview; import sys; root=Path(sys.argv[1]); write_preview(root/"menu"); write_preview(root/"gallery", mode="gallery")', work], {stdio:'inherit'});
  const chrome = process.env.CHROME || 'google-chrome';
  browser = spawn(chrome, ['--headless=new','--disable-background-networking','--disable-component-update',
    '--disable-sync','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',
    '--user-data-dir='+join(work,'profile'),'about:blank'], {stdio:'ignore'});
  let port;
  await waitFor(async () => {
    const data = await readFile(join(work,'profile','DevToolsActivePort'),'utf8');
    port = Number(data.split('\n')[0]);
    return port > 0;
  }, 'Chromium startup');
  const info = await (await fetch('http://127.0.0.1:'+port+'/json/version')).json();
  ws = new WebSocket(info.webSocketDebuggerUrl);
  await new Promise((ok, fail) => {
    ws.addEventListener('open',ok,{once:true});
    ws.addEventListener('error',fail,{once:true});
  });
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const job = pending.get(message.id);
      if (!job) return;
      pending.delete(message.id);
      clearTimeout(job.timeout);
      if (message.error) job.fail(new Error('CDP error: '+message.error.message));
      else job.ok(message.result);
    } else if (['Log.entryAdded','Runtime.exceptionThrown','Network.requestWillBeSent'].includes(message.method)) {
      if (events.length < 500) events.push(message);
    }
  });
  const target = await request('Target.createTarget',{url:'about:blank'},null);
  session = (await request('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
  await request('Page.enable'); await request('Runtime.enable'); await request('Log.enable'); await request('Network.enable');
  await navigate('menu',1280,900);
  assert.equal(await evaluate('document.getAnimations().length'),0,'menu must rest quietly');
  await screenshot('menu-desktop-rest');
  await key('Tab','Tab',9);
  assert.equal(await evaluate('document.activeElement.id'), 'motion-off');
  await key('Tab','Tab',9);
  assert.equal(await evaluate('document.activeElement.parentElement.id'), 'section-agents');
  await key('Enter','Enter',13);
  await waitFor(() => evaluate('document.querySelector("#section-agents").open'), 'keyboard open');
  await delay(70);
  await screenshot('menu-desktop-impact');
  await delay(550);
  await screenshot('menu-desktop-settled');
  await key('Enter','Enter',13);
  await waitFor(() => evaluate('!document.querySelector("#section-agents").open'), 'keyboard close');
  await click('#section-settings summary');
  await waitFor(() => evaluate('document.querySelector("#section-settings").open'), 'mouse open');
  assert.equal(await evaluate('getComputedStyle(document.querySelector("#section-settings .effect")).animationName'),'vx-impact');
  assert.equal(await evaluate('getComputedStyle(document.querySelector("#section-settings .fx")).animationName'),'vx-vector');
  for (const ms of [0,80,180,420]) {
    await evaluate('document.getAnimations().forEach(a=>{a.pause();a.currentTime='+ms+'})');
    await screenshot('motion-frame-'+ms);
  }
  await evaluate('document.getAnimations().forEach(a=>a.finish())');
  await click('#section-settings summary');
  await waitFor(() => evaluate('!document.querySelector("#section-settings").open'), 'mouse close');

  await navigate('menu',390,844);
  await screenshot('menu-phone-rest');
  await click('#section-functions summary',true);
  await waitFor(() => evaluate('document.querySelector("#section-functions").open'), 'touch open');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  await delay(500);
  await screenshot('menu-phone-expanded');

  await navigate('gallery',390,844);
  assert.equal(await evaluate('document.getAnimations().length'),0,'initial controls must rest quietly');
  await click('input[role="switch"]',true);
  await waitFor(() => evaluate('document.querySelector("input[role=switch]").checked'), 'switch touch');
  await click('#choice-1',true);
  await waitFor(() => evaluate('document.querySelector("#choice-1").checked'), 'radio touch');
  await click('#demo-range',true);
  const oldRange = await evaluate('document.querySelector("#demo-range").valueAsNumber');
  await evaluate('document.querySelector("#demo-range").focus()');
  await key('ArrowRight','ArrowRight',39);
  assert.equal(await evaluate('document.querySelector("#demo-range").valueAsNumber'),oldRange+1);
  await evaluate('document.querySelector("#demo-text").focus()');
  await request('Input.insertText',{text:'VorteX'});
  assert.equal(await evaluate('document.querySelector("#demo-text").value'),'VorteX');
  await click('#demo-segment-1',true);
  await waitFor(() => evaluate('document.querySelector("#demo-segment-1").checked'), 'segmented touch');
  await click('#demo-rating-4',true);
  await waitFor(() => evaluate('document.querySelector("#demo-rating-4").checked'), 'rating touch');
  await evaluate('document.querySelector("#demo-select").focus()');
  await key('ArrowDown','ArrowDown',40);
  await waitFor(() => evaluate('document.querySelector("#demo-select").selectedIndex === 1'), 'select keyboard');
  await click('#demo-notice summary',true);
  await waitFor(() => evaluate('document.querySelector("#demo-notice").open'), 'notice touch');
  await click('#motion-off',true);
  await waitFor(() => evaluate('document.querySelector("#motion-off").checked'), 'motion switch');
  assert.equal(await evaluate('getComputedStyle(document.querySelector(".field:has(input:checked) .effect")).animationName'),'none');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true,'gallery horizontal overflow');
  await screenshot('gallery-phone-motion-off');

  await navigate('menu',390,844,true);
  await click('#section-security summary',true);
  await waitFor(() => evaluate('document.querySelector("#section-security").open'), 'reduced-motion touch');
  assert.equal(await evaluate('getComputedStyle(document.querySelector("#section-security .effect")).animationName'),'none');
  assert.equal(await evaluate('getComputedStyle(document.querySelector("#section-security .fx")).visibility'),'hidden');
  await screenshot('menu-phone-reduced-motion');

  const errors = events.filter(e=>e.method==='Runtime.exceptionThrown'||(e.method==='Log.entryAdded'&&e.params.entry.level==='error'));
  assert.equal(errors.length,0,'Browser errors or CSP violations');
  const remote = events.filter(e=>e.method==='Network.requestWillBeSent'&&/^https?:/.test(e.params.request.url));
  assert.equal(remote.length,0,'Preview made network requests');
  const report={status:'PASS',browser:info.Browser,widths:[1280,390],keyboard:true,mouse:true,touch_emulated:true,quiet_rest:true,vector_animation:true,stepped_animation_ms:[0,80,180,420],
    range_keyboard:true,text_input:true,segmented:true,rating:true,select_keyboard:true,notice:true,reduced_motion:true,local_motion_switch:true,
    no_horizontal_overflow:true,network_requests:remote.length,browser_errors:errors.length,
    limitations:'Headless Chromium; no physical phone, Safari, Firefox or screen reader.'};
  await writeFile(join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log('MOTION_BROWSER '+JSON.stringify(report));
} finally {
  if (ws) ws.close();
  if (browser) {
    browser.kill();
    await Promise.race([new Promise(ok=>browser.once('exit',ok)),delay(1500)]);
  }
  await rm(work,{recursive:true,force:true,maxRetries:3});
}
