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
  '--remote-debugging-port=9224',
  '--window-size=1440,900',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  'about:blank',
], { stdio: 'ignore' })

async function waitForPort(retries = 30) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9224/json/version')
      if (res.ok) return true
    } catch {}
    await new Promise(r => setTimeout(r, 200))
  }
  return false
}

const isReady = await waitForPort()
if (!isReady) {
  console.error('[!] Edge CDP failed to start on port 9224')
  edgeProc.kill()
  process.exit(1)
}

const baseUrl = 'http://127.0.0.1:8000'
console.log(`[*] Testing interactive flows on: ${baseUrl}`)

const newTabRes = await fetch(`http://127.0.0.1:9224/json/new?${encodeURIComponent(baseUrl)}`, { method: 'PUT' })
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

// 1. Navigate to base URL
console.log('[*] Navigating to page...')
await sendCommand(10, 'Page.navigate', { url: baseUrl })
await new Promise(r => setTimeout(r, 4000))

// 2. Click "Complete Setup & Launch Privora" button if present
console.log('[*] Testing Onboarding completion click...')
const wizardClickResult = await sendCommand(20, 'Runtime.evaluate', {
  expression: `(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const completeBtn = buttons.find(b => b.textContent.includes('Complete Setup') || b.textContent.includes('Launch Privora'));
    if (completeBtn) {
      completeBtn.click();
      return { clicked: true, text: completeBtn.textContent };
    }
    return { clicked: false };
  })()`,
  returnByValue: true,
})
console.log('[*] Onboarding button interaction:', wizardClickResult?.result?.value)

await new Promise(r => setTimeout(r, 1500))

// 3. Test clicking tabs
const tabs = ['Document library', 'AI research', 'Evidence explorer', 'Privacy & security', 'Settings', 'Overview']
for (let i = 0; i < tabs.length; i++) {
  const tabName = tabs[i]
  console.log(`[*] Clicking tab: "${tabName}"...`)
  const clickRes = await sendCommand(30 + i, 'Runtime.evaluate', {
    expression: `(() => {
      const links = Array.from(document.querySelectorAll('button, a, [role=\"tab\"], .nav-item'));
      const target = links.find(el => el.textContent.trim().toLowerCase() === ${JSON.stringify(tabName.toLowerCase())});
      if (target) {
        target.click();
        return { clicked: true, found: true };
      }
      return { clicked: false, found: false };
    })()`,
    returnByValue: true,
  })
  console.log(`    Result: ${JSON.stringify(clickRes?.result?.value)}`)
  await new Promise(r => setTimeout(r, 1000))
}

// Check final state
const finalCheck = await sendCommand(99, 'Runtime.evaluate', {
  expression: `(() => {
    return {
      title: document.title,
      hasObjectObject: document.body.innerHTML.includes('[object Object]'),
      activeTab: document.querySelector('.active, [aria-selected=\"true\"]')?.textContent?.trim() || 'unknown',
    };
  })()`,
  returnByValue: true,
})

console.log('[*] Final interactive state:', JSON.stringify(finalCheck?.result?.value, null, 2))

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

assert.strictEqual(finalCheck?.result?.value?.hasObjectObject, false, 'Detected [object Object] in HTML!')
assert.strictEqual(capturedErrors.length, 0, 'Encountered console errors during interactive navigation!')
assert.strictEqual(relevantWarnings.length, 0, 'Encountered React warnings during interactive navigation!')

console.log('[OK] INTERACTIVE NAVIGATION TEST PASSED 100% CLEANLY!')
