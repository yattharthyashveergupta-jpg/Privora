import { spawn } from 'node:child_process'
import assert from 'node:assert'
import fs from 'node:fs'

const edgePaths = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  `${process.env.LOCALAPPDATA}\\Microsoft\\Edge\\Application\\msedge.exe`,
]

const edgeExe = edgePaths.find(p => fs.existsSync(p))
if (!edgeExe) {
  console.log('[!] Edge browser not found on host.')
  process.exit(1)
}

const edgeProc = spawn(edgeExe, [
  '--headless',
  '--remote-debugging-port=9223',
  '--window-size=1440,900',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank',
], { stdio: 'ignore' })

async function waitForPort(retries = 30) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9223/json/version')
      if (res.ok) return true
    } catch {}
    await new Promise(r => setTimeout(r, 200))
  }
  return false
}

const isReady = await waitForPort()
if (!isReady) {
  console.error('[!] Edge CDP failed to start on port 9223')
  edgeProc.kill()
  process.exit(1)
}

const baseUrl = process.argv[2] || 'http://127.0.0.1:8000'
console.log(`[*] Testing full dashboard on: ${baseUrl}`)

const newTabRes = await fetch(`http://127.0.0.1:9223/json/new?${encodeURIComponent(baseUrl)}`, { method: 'PUT' })
const tabInfo = await newTabRes.json()
const ws = new WebSocket(tabInfo.webSocketDebuggerUrl)

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
    if (level === 'error') capturedErrors.push(text)
    else if (level === 'warning') capturedWarnings.push(text)
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

await sendCommand(10, 'Page.navigate', { url: baseUrl })

// Wait for initial render
await new Promise(r => setTimeout(r, 4000))

// Inspect page elements
const pageEval = await sendCommand(20, 'Runtime.evaluate', {
  expression: `(() => {
    const buttons = Array.from(document.querySelectorAll('button')).map(b => b.textContent.trim()).filter(Boolean);
    const navItems = Array.from(document.querySelectorAll('nav a, [role="tab"], .nav-item')).map(el => el.textContent.trim()).filter(Boolean);
    const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.textContent.trim()).filter(Boolean);
    const bodyText = document.body ? document.body.innerText.slice(0, 500) : '';
    return {
      title: document.title,
      buttonsCount: buttons.length,
      headings,
      navItems,
      bodyPreview: bodyText,
      hasObjectObject: document.body.innerHTML.includes('[object Object]'),
    };
  })()`,
  returnByValue: true,
})

console.log('[*] Page Evaluation Result:', JSON.stringify(pageEval?.result?.value, null, 2))

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

const evalResult = pageEval?.result?.value
assert.ok(evalResult, 'Failed to evaluate page')
assert.strictEqual(evalResult.hasObjectObject, false, 'Found [object Object] in page HTML!')
assert.strictEqual(capturedErrors.length, 0, 'Console errors encountered on homepage!')
assert.strictEqual(relevantWarnings.length, 0, 'React warnings encountered on homepage!')

console.log('[OK] Dashboard homepage & navigation verified 100% clean!')
