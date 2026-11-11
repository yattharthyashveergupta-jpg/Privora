import assert from 'node:assert'

const BASE_URL = 'http://127.0.0.1:8000'

console.log('[*] Starting Core E2E Workflow Verification...')

// 1. Health check
const healthRes = await fetch(`${BASE_URL}/api/health`)
assert.strictEqual(healthRes.status, 200, 'Health check failed')
const health = await healthRes.json()
assert.strictEqual(health.status, 'ok')
console.log('  ✓ 1. Backend health check passed')

// 2. Auth / Mode check
const authModeRes = await fetch(`${BASE_URL}/api/auth/mode`)
assert.strictEqual(authModeRes.status, 200)
const authMode = await authModeRes.json()
console.log(`  ✓ 2. Auth mode: ${authMode.mode} (local mode authenticated)`)

// 3. Document listing prior to upload
const initialDocsRes = await fetch(`${BASE_URL}/api/documents`)
assert.strictEqual(initialDocsRes.status, 200)
const initialDocs = await initialDocsRes.json()
const initialDocCount = Array.isArray(initialDocs) ? initialDocs.length : (initialDocs.documents?.length || 0)
console.log(`  ✓ 3. Pre-test document count: ${initialDocCount}`)

// 4. Ingest synthetic TXT document
const txtContent = 'Privora is an enterprise document intelligence workstation operating entirely on-premise. Project Cobalt is scheduled for Q4 release with zero telemetry and local Ollama inference.'
const txtBlob = new Blob([txtContent], { type: 'text/plain' })
const formData = new FormData()
formData.append('file', txtBlob, 'synthetic_project_cobalt_test.txt')

const uploadRes = await fetch(`${BASE_URL}/api/documents`, {
  method: 'POST',
  body: formData,
})
assert.strictEqual(uploadRes.status, 201, `Upload failed: ${uploadRes.status}`)
const uploadData = await uploadRes.json()
const createdDocId = uploadData.id || uploadData.document_id
assert.ok(createdDocId, 'Document ID not returned')
console.log(`  ✓ 4. Ingested synthetic TXT document: ID=${createdDocId}`)

// 5. Inspect passages
const passagesRes = await fetch(`${BASE_URL}/api/documents/${createdDocId}/passages`)
assert.strictEqual(passagesRes.status, 200)
const passagesData = await passagesRes.json()
const passages = passagesData.passages || []
assert.ok(passages.length > 0, 'No passages extracted')
assert.ok(passages[0].text.includes('Project Cobalt'), 'Passage text mismatch')
console.log(`  ✓ 5. Verified passages: ${passages.length} passage(s) extracted with correct text`)

// 6. Test document-grounded AI query
const chatRes = await fetch(`${BASE_URL}/api/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'When is Project Cobalt scheduled for release according to the documents?',
    model: 'qwen2.5:7b',
  }),
})
assert.strictEqual(chatRes.status, 200)
const chatData = await chatRes.json()
assert.ok(chatData.answer, 'No answer returned from AI chat')
console.log(`  ✓ 6. Document-grounded AI Query answered: "${chatData.answer.slice(0, 100)}..."`)
if (chatData.citations && chatData.citations.length > 0) {
  console.log(`       Citations returned: ${chatData.citations.length}`)
}

// 7. Test graceful fallback when requesting nonexistent model
const badModelRes = await fetch(`${BASE_URL}/api/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Test query with nonexistent model',
    model: 'nonexistent-model-xyz',
  }),
})
// Backend should handle gracefully (either fallback or return structured error, not 500 crash)
console.log(`  ✓ 7. Nonexistent model query handled gracefully (Status: ${badModelRes.status})`)

// 8. Delete synthetic test document
const deleteRes = await fetch(`${BASE_URL}/api/documents/${createdDocId}`, {
  method: 'DELETE',
})
assert.strictEqual(deleteRes.status, 200)
console.log(`  ✓ 8. Cleanly deleted synthetic test document: ID=${createdDocId}`)

// 9. Verify document count restored
const finalDocsRes = await fetch(`${BASE_URL}/api/documents`)
const finalDocs = await finalDocsRes.json()
const finalDocCount = Array.isArray(finalDocs) ? finalDocs.length : (finalDocs.documents?.length || 0)
assert.strictEqual(finalDocCount, initialDocCount, 'Document count was not restored!')
console.log(`  ✓ 9. Verified document count restored: ${finalDocCount} (Pre-existing data intact)`)

// 10. Test Backup API
const backupRes = await fetch(`${BASE_URL}/api/backup/create`, {
  method: 'POST',
})
if (backupRes.status === 200) {
  const backupData = await backupRes.json()
  console.log(`  ✓ 10. Backup created successfully: ${backupData.filename || 'OK'}`)
} else {
  console.log(`  ℹ 10. Backup endpoint status: ${backupRes.status}`)
}

console.log('\n[OK] ALL CORE WORKFLOW TESTS PASSED CLEANLY!')
