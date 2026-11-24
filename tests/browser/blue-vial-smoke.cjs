#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const { readFile } = require('node:fs/promises');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const gameRoot = path.resolve(__dirname, '../../demos/blue-vial-browser-game');
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/three.min.js', ['three.min.js', 'text/javascript; charset=utf-8']],
  ['/scenarios.js', ['scenarios.js', 'text/javascript; charset=utf-8']],
]);

async function main() {
  const html = await readFile(path.join(gameRoot, 'index.html'), 'utf8');
  await readFile(path.join(gameRoot, 'three.min.js'));
  const scenarios = await readFile(path.join(gameRoot, 'scenarios.js'), 'utf8');
  assert.match(html, /<script\s+src=["']\.\/three\.min\.js["']/i, 'page must load its local Three.js runtime');
  assert.doesNotMatch(html, /<script\b[^>]*\bsrc=["']https?:\/\//i, 'page must not load external scripts');
  // Keep the real WebGL scene and state machine, but shorten mock waypoint timers for CI.
  const durations = html.match(/duration:(?:\d+(?:\.\d+)?|\.\d+)/g) || [];
  assert.equal(durations.length, 9, 'expected the nine mock waypoints to be present');
  const smokeHtml = html.replace(/duration:(?:\d+(?:\.\d+)?|\.\d+)/g, 'duration:0.04');
  assert.match(scenarios, /const SCENARIO_RUN_SECONDS = 4;/, 'scenario runtime should keep its normal four-second mock duration');
  const smokeScenarios = scenarios.replace('const SCENARIO_RUN_SECONDS = 4;', 'const SCENARIO_RUN_SECONDS = 0.8;');

  const server = http.createServer(async (req, res) => {
    const pathname = new URL(req.url, 'http://127.0.0.1').pathname;
    const file = files.get(pathname);
    if (!file) {
      res.writeHead(404);
      res.end('not found');
      return;
    }
    try {
      const body = file[0] === 'index.html'
        ? Buffer.from(smokeHtml)
        : file[0] === 'scenarios.js'
          ? Buffer.from(smokeScenarios)
          : await readFile(path.join(gameRoot, file[0]));
      res.writeHead(200, {
        'content-type': file[1],
        'cache-control': 'no-store',
        'x-content-type-options': 'nosniff',
      });
      res.end(body);
    } catch (error) {
      res.writeHead(500);
      res.end(String(error));
    }
  });

  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });

  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      executablePath: process.env.CHROME_BIN || undefined,
      args: [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
      ],
    });
    const page = await browser.newPage({ viewport: { width: 960, height: 720 } });
    const pageErrors = [];
    const consoleErrors = [];
    const failedRequests = [];
    const externalRequests = [];
    const origin = `http://127.0.0.1:${server.address().port}`;

    page.on('pageerror', error => pageErrors.push(error.stack || error.message));
    page.on('console', message => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('requestfailed', request => {
      failedRequests.push(`${request.url()}: ${request.failure()?.errorText || 'request failed'}`);
    });
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.protocol !== 'data:' && url.origin !== origin) externalRequests.push(request.url());
    });

    const response = await page.goto(origin, { waitUntil: 'load', timeout: 15000 });
    assert.equal(response.status(), 200, 'game page should return HTTP 200');
    await page.waitForFunction(() => {
      const canvas = document.querySelector('#viewport canvas');
      return canvas && canvas.width > 0 && canvas.height > 0;
    }, null, { timeout: 10000 });
    assert.match(await page.locator('#statusBadge').textContent(), /READY \/ MOCK/);
    assert.equal(await page.locator('#bboxToggle').textContent(), '□ BBOX ON');
    assert.deepEqual(
      await page.locator('#scenarioSelect option').evaluateAll(options => options.map(option => [option.value, option.textContent.trim()])),
      [
        ['blue-vial', 'Blue Vial · 藥瓶抓取'],
        ['delivery', '餐飲配送 · 送餐機器人'],
        ['laser-coating', '半導體實驗室 · 雷射鍍膜'],
      ],
      'all three mock scenarios should be selectable',
    );

    await page.locator('#lightRange').evaluate(element => {
      element.value = '710';
      element.dispatchEvent(new Event('input', { bubbles: true }));
    });
    assert.equal((await page.locator('#lightVal').textContent()).trim(), '710 lx');

    await page.locator('#bboxToggle').click();
    assert.equal(await page.locator('#bbox').evaluate(element => getComputedStyle(element).display), 'none');
    await page.locator('#bboxToggle').click();
    assert.notEqual(await page.locator('#bbox').evaluate(element => getComputedStyle(element).display), 'none');

    await page.locator('#runBtn').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('COMPLETE'),
      null,
      { timeout: 30000 },
    );
    assert.equal((await page.locator('#pickCount').textContent()).trim(), '01');
    assert.equal((await page.locator('#stepCounter').textContent()).trim(), '6 / 6');

    await page.locator('[data-mode="HIL"]').click();
    assert.equal(await page.locator('#confirmBtn').isVisible(), true);
    await page.locator('#runBtn').click();
    assert.match(await page.locator('#toast').textContent(), /HIL 模式需要先確認/);
    await page.locator('#confirmBtn').click();
    await page.locator('#runBtn').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('RUNNING'),
      null,
      { timeout: 2000 },
    );
    await page.locator('#estop').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('E-STOP LATCHED'),
      null,
      { timeout: 2000 },
    );
    assert.equal(await page.locator('#estop').evaluate(element => element.classList.contains('latched')), true);
    await page.locator('#runBtn').click();
    assert.match(await page.locator('#toast').textContent(), /急停鎖存中/);
    await page.locator('#resetEstop').click();
    assert.equal(await page.locator('#estop').evaluate(element => element.classList.contains('latched')), false);
    assert.match(await page.locator('#statusBadge').textContent(), /HIL \/ READY · MOCK/);

    await page.locator('#scenarioSelect').selectOption('delivery');
    assert.equal((await page.locator('.target-name').textContent()).trim(), 'MEAL TRAY');
    assert.match(await page.locator('.footer-right .warning').textContent(), /NO REAL DELIVERY/);
    assert.match(await page.locator('.mock-note').textContent(), /沒有真實導航/);
    await page.locator('#runBtn').click();
    assert.match(await page.locator('#toast').textContent(), /HIL 模式需要先確認/);
    await page.locator('#confirmBtn').click();
    await page.locator('#runBtn').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('COMPLETE'),
      null,
      { timeout: 7000 },
    );
    assert.equal((await page.locator('#phaseMetric').textContent()).trim(), '完成');
    assert.equal((await page.locator('#stepCounter').textContent()).trim(), '4 / 4');
    assert.equal((await page.locator('#pickCount').textContent()).trim(), '01');

    await page.locator('#scenarioSelect').selectOption('laser-coating');
    assert.equal((await page.locator('.target-name').textContent()).trim(), 'SILICON WAFER');
    assert.match(await page.locator('.footer-right .warning').textContent(), /NO LASER.*NO MATERIAL PROCESS/);
    assert.match(await page.locator('.mock-note').textContent(), /沒有雷射發射、材料沉積/);
    await page.locator('#runBtn').click();
    assert.match(await page.locator('#toast').textContent(), /HIL 模式需要先確認/);
    await page.locator('#confirmBtn').click();
    await page.locator('#runBtn').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('RUNNING'),
      null,
      { timeout: 2000 },
    );
    await page.locator('#estop').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('E-STOP LATCHED'),
      null,
      { timeout: 2000 },
    );
    assert.equal(await page.locator('#estop').evaluate(element => element.classList.contains('latched')), true);
    await page.locator('#runBtn').click();
    assert.match(await page.locator('#toast').textContent(), /急停鎖存中/);
    await page.locator('#resetEstop').click();
    assert.equal(await page.locator('#estop').evaluate(element => element.classList.contains('latched')), false);
    await page.locator('#confirmBtn').click();
    await page.locator('#runBtn').click();
    await page.waitForFunction(
      () => document.querySelector('#statusBadge').textContent.includes('COMPLETE'),
      null,
      { timeout: 7000 },
    );
    assert.equal((await page.locator('#stepCounter').textContent()).trim(), '4 / 4');
    assert.equal((await page.locator('#pickCount').textContent()).trim(), '01');

    await page.locator('#scenarioSelect').selectOption('blue-vial');
    assert.equal((await page.locator('.target-name').textContent()).trim(), 'BLUE VIAL');
    assert.match(await page.locator('.mock-note').textContent(), /未執行 Isaac Sim/);

    assert.deepEqual(pageErrors, [], 'page should not throw JavaScript exceptions');
    assert.deepEqual(consoleErrors, [], 'browser console should not report errors');
    assert.deepEqual(failedRequests, [], 'all local page assets should load');
    assert.deepEqual(externalRequests, [], 'game runtime should not fetch external resources');
    console.log('PASS: Chromium loaded the local 3D scene and exercised randomization, BBOX, Blue Vial, delivery and laser mock completion, HIL gates, and E-STOP.');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
