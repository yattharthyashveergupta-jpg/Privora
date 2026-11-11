import { spawn } from 'node:child_process'
import assert from 'node:assert'
import fs from 'node:fs'

console.log('[*] Starting Edge in headless debugging mode for full UI verification...')

const edgePaths = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  `${process.env.LOCALAPPDATA}\\Microsoft\\Edge\\Application\\msedge.exe`,
]

const edgeExe = edgePaths.find(p => fs.existsSync(p))

if (!edgeExe) {
  console.log('[!] Edge browser not found on host. Skipping browser automation.')
  process.exit(0)
}

const edgeProc = spawn(edgeExe, [
  '--headless',
  '--remote-debugging-port=9222',
  '--window-size=1440,900',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank',
], { stdio: 'ignore' })

async function waitForPort(retries = 30) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9222/json/version')
      if (res.ok) return true
    } catch {}
    await new Promise(r => setTimeout(r, 200))
  }
  return false
}

const isReady = await waitForPort()
if (!isReady) {
  console.error('[!] Edge CDP failed to start on port 9222')
  edgeProc.kill()
  process.exit(1)
}

const targetUrl = process.argv[2] || 'http://127.0.0.1:8000/#wizard'
console.log(`[*] Target URL: ${targetUrl}`)
const newTabRes = await fetch(`http://127.0.0.1:9222/json/new?${encodeURIComponent(targetUrl)}`, { method: 'PUT' })
const tabInfo = await newTabRes.json()
const wsUrl = tabInfo.webSocketDebuggerUrl

const ws = new WebSocket(wsUrl)

const capturedErrors = []
const capturedWarnings = []

await new Promise((resolve) => {
  ws.onopen = () => {
    ws.send(JSON.stringify({ id: 1, method: 'Console.enable' }))
    ws.send(JSON.stringify({ id: 2, method: 'Runtime.enable' }))
    ws.send(JSON.stringify({ id: 3, method: 'Page.enable' }))
    resolve()
  }
})

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)
  if (msg.method === 'Console.messageAdded') {
    const text = msg.params.message.text
    const level = msg.params.message.level
    if (level === 'error') {
      capturedErrors.push(text)
    } else if (level === 'warning') {
      capturedWarnings.push(text)
    }
  } else if (msg.method === 'Runtime.exceptionThrown') {
    const details = msg.params.exceptionDetails
    capturedErrors.push(details.text + ' ' + (details.exception?.description || ''))
  }
}

function sendCommand(id, method, params = {}) {
  return new Promise((resolve) => {
    const handler = (evt) => {
      const data = JSON.parse(evt.data)
      if (data.id === id) {
        ws.removeEventListener('message', handler)
        resolve(data.result)
      }
    }
    ws.addEventListener('message', handler)
    ws.send(JSON.stringify({ id, method, params }))
  })
}

// Navigate via Page.navigate
console.log(`[*] Navigating to ${targetUrl} via Page.navigate...`)
await sendCommand(5, 'Page.navigate', { url: targetUrl })

console.log('[*] Waiting for scripts to execute and React hydration...')

async function pollForModal(timeoutMs = 12000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const res = await sendCommand(30, 'Runtime.evaluate', {
      expression: `(() => {
        const modalCard = document.querySelector('.modal-card');
        const badge = modalCard ? modalCard.querySelector('.hero-status-badge') : null;
        const select = modalCard ? modalCard.querySelector('select') : null;
        const options = select ? Array.from(select.querySelectorAll('option')).map(o => ({
          value: o.value,
          text: o.text,
        })) : [];
        const specCard = modalCard ? modalCard.querySelector('.modal-body strong') : null;
        return {
          url: window.location.href,
          hash: window.location.hash,
          modalFound: Boolean(modalCard),
          modalTitle: badge ? badge.textContent : null,
          selectFound: Boolean(select),
          selectedValue: select ? select.value : null,
          optionsCount: options.length,
          options,
          specCardText: specCard ? specCard.textContent : null,
        };
      })()`,
      returnByValue: true,
    })
    if (res?.result?.value?.modalFound) return res.result.value
    await new Promise(r => setTimeout(r, 600))
  }
  return null
}

const modalInspection = await pollForModal()
console.log('[*] Modal inspection details:', JSON.stringify(modalInspection, null, 2))

ws.close()
edgeProc.kill()

console.log(`[*] Total Console Errors: ${capturedErrors.length}`)
for (const err of capturedErrors) {
  console.log(`    ERROR: ${err}`)
}

const relevantWarnings = capturedWarnings.filter(w => w.includes('key') || w.includes('React') || w.includes('duplicate'))
console.log(`[*] Total Relevant Warnings: ${relevantWarnings.length}`)
for (const w of relevantWarnings) {
  console.log(`    WARNING: ${w}`)
}

// Assertions
const duplicateKeyErrors = capturedWarnings.filter(w => w.includes('[object Object]') || w.includes('duplicate key') || w.includes('same key'))
const objectChildErrors = capturedErrors.filter(e => e.includes('Objects are not valid as a React child') || e.includes('download_size'))

assert.strictEqual(duplicateKeyErrors.length, 0, 'Found duplicate key warnings!')
assert.strictEqual(objectChildErrors.length, 0, 'Found object-as-React-child errors!')

const inspectData = modalInspection
assert.ok(inspectData, 'modalInspection was null!')
assert.strictEqual(inspectData.modalFound, true, 'OnboardingModal was not found!')
assert.strictEqual(inspectData.selectFound, true, 'Model select element was not found!')
assert.ok(inspectData.optionsCount >= 1, 'Expected at least 1 model option in select!')

// Verify that NO option has value or text with "[object Object]"
for (const opt of inspectData.options) {
  assert.ok(!opt.value.includes('[object Object]'), `Option value contained [object Object]: ${opt.value}`)
  assert.ok(!opt.text.includes('[object Object]'), `Option text contained [object Object]: ${opt.text}`)
  console.log(`  ✓ Verified option: value="${opt.value}" | text="${opt.text}"`)
}

console.log('[OK] ALL BROWSER RUNTIME VERIFICATIONS PASSED 100% CLEANLY!')
