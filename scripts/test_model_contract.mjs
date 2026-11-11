import assert from 'node:assert'
import {
  DEFAULT_RECOMMENDED_MODELS,
  normalizeModelMetadata,
  deduplicateModels,
} from '../lib/api.ts'

console.log('[*] Testing model metadata contract & normalization...')

// 1. String input normalization
const fromString = normalizeModelMetadata('llama3.2:3b', true)
assert.strictEqual(fromString.name, 'llama3.2:3b')
assert.strictEqual(fromString.tag, 'llama3.2:3b')
assert.strictEqual(fromString.label, 'llama3.2:3b')
assert.strictEqual(fromString.installed, true)
console.log('  ✓ String input normalization passed')

// 2. Object input normalization
const fromObj = normalizeModelMetadata({
  name: 'qwen2.5:7b',
  tag: 'qwen2.5:7b',
  label: 'Qwen 2.5 (7B) — Recommended Balanced',
  download_size: '~4.7 GB',
  ram_required: '8 GB+ RAM / VRAM',
  is_default: true,
  installed: true,
})
assert.strictEqual(fromObj.name, 'qwen2.5:7b')
assert.strictEqual(fromObj.tag, 'qwen2.5:7b')
assert.strictEqual(fromObj.label, 'Qwen 2.5 (7B) — Recommended Balanced')
assert.strictEqual(fromObj.download_size, '~4.7 GB')
assert.strictEqual(fromObj.ram_required, '8 GB+ RAM / VRAM')
assert.strictEqual(fromObj.is_default, true)
assert.strictEqual(fromObj.installed, true)
console.log('  ✓ Object input normalization passed')

// 3. Fallback for malformed or missing fields
const malformed = normalizeModelMetadata({ foo: 'bar' })
assert.strictEqual(malformed.tag, 'unknown')
assert.strictEqual(malformed.label, 'unknown')
assert.strictEqual(malformed.is_default, false)
assert.strictEqual(malformed.installed, false)
console.log('  ✓ Malformed object safety fallback passed')

// 4. Deduplication
const withDups = [
  { name: 'qwen2.5:7b', tag: 'qwen2.5:7b', label: 'Qwen 2.5 7B' },
  { name: 'QWEN2.5:7B', tag: 'Qwen2.5:7b', label: 'Qwen 2.5 7B Duplicate' },
  { name: 'llama3:8b', tag: 'llama3:8b', label: 'Llama 3 8B' },
]
const deduped = deduplicateModels(withDups)
assert.strictEqual(deduped.length, 2)
assert.strictEqual(deduped[0].tag, 'qwen2.5:7b')
assert.strictEqual(deduped[1].tag, 'llama3:8b')
console.log('  ✓ Case-insensitive deduplication passed')

// 5. Verification of React key uniqueness and absence of '[object Object]'
const installed = deduplicateModels(['qwen2.5:7b', 'llama3:8b'].map(m => normalizeModelMetadata(m, true)))
const recommended = deduplicateModels(DEFAULT_RECOMMENDED_MODELS.map(m => normalizeModelMetadata(m, false)))

const installedTagSet = new Set(installed.map(m => m.tag.toLowerCase()))
const uninstalledRecommended = recommended.filter(
  m => !installedTagSet.has(m.tag.toLowerCase()) && !installedTagSet.has(m.name.toLowerCase())
)

const generatedKeys = []
for (const m of installed) {
  const key = `installed-${m.tag}`
  assert.doesNotMatch(key, /\[object Object\]/)
  assert.strictEqual(typeof key, 'string')
  generatedKeys.push(key)
}
for (const m of uninstalledRecommended) {
  const key = `rec-${m.tag}`
  assert.doesNotMatch(key, /\[object Object\]/)
  assert.strictEqual(typeof key, 'string')
  generatedKeys.push(key)
}

// Ensure all keys are 100% unique
const uniqueKeys = new Set(generatedKeys)
assert.strictEqual(uniqueKeys.size, generatedKeys.length)
console.log(`  ✓ Generated ${generatedKeys.length} unique React keys without any '[object Object]'`)

// 6. Verification that uninstalledRecommended does NOT contain qwen2.5:7b (which is installed)
assert.strictEqual(uninstalledRecommended.some(m => m.tag.toLowerCase() === 'qwen2.5:7b'), false)
console.log('  ✓ Installed model exclusion from recommended list passed')

console.log('[OK] All frontend model normalization & contract tests passed!')
