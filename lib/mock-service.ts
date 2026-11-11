export type MockDocument = { id: string; filename: string; type: 'PDF' | 'DOCX' | 'TXT'; size: number; status: 'indexed' | 'processing' | 'failed' | 'duplicate'; pages: number; createdAt: string; hash: string }
export type MockCitation = { documentId: string; filename: string; page?: number; excerpt: string }
export type MockChatResponse = { answer: string; citations: MockCitation[]; insufficientEvidence: boolean }

const seed: MockDocument[] = [
  { id: 'doc-brief', filename: 'Q3-operations-brief.pdf', type: 'PDF', size: 1840000, status: 'indexed', pages: 12, createdAt: '2026-10-21', hash: 'a91f' },
  { id: 'doc-policy', filename: 'data-retention-policy.docx', type: 'DOCX', size: 382000, status: 'indexed', pages: 4, createdAt: '2026-10-19', hash: 'b204' },
  { id: 'doc-notes', filename: 'field-notes.txt', type: 'TXT', size: 92000, status: 'indexed', pages: 1, createdAt: '2026-10-17', hash: 'c8e1' },
]
let documents = [...seed]
const evidence: MockCitation[] = [
  { documentId: 'doc-brief', filename: 'Q3-operations-brief.pdf', page: 6, excerpt: 'The operations team will prioritize incident response consistency, measurable handoffs, and a weekly review of unresolved risks.' },
  { documentId: 'doc-policy', filename: 'data-retention-policy.docx', page: 2, excerpt: 'Working documents are retained for the duration of the active project and should be removed when the business purpose ends.' },
]
export const mockService = {
  list: async () => [...documents],
  upload: async (file: File, onStatus?: (status: string) => void) => {
    const type = file.name.split('.').pop()?.toUpperCase()
    if (!['PDF', 'DOCX', 'TXT'].includes(type ?? '')) throw new Error('Unsupported file type. Use PDF, DOCX, or TXT.')
    if (file.size > 25 * 1024 * 1024) throw new Error('File exceeds the 25 MB local upload limit.')
    if (documents.some((doc) => doc.filename.toLowerCase() === file.name.toLowerCase())) throw new Error('Duplicate detected. This filename is already in the library.')
    onStatus?.('Validating locally…'); await delay(420); onStatus?.('Indexing document…'); await delay(620)
    const item: MockDocument = { id: `doc-${Date.now()}`, filename: file.name, type: type as MockDocument['type'], size: file.size, status: 'indexed', pages: type === 'TXT' ? 1 : 3, createdAt: new Date().toISOString().slice(0, 10), hash: 'local' }
    documents = [item, ...documents]; return item
  },
  remove: async (id: string) => { await delay(280); documents = documents.filter((doc) => doc.id !== id) },
  evidence: async (term = '') => evidence.filter((item) => !term || `${item.filename} ${item.excerpt}`.toLowerCase().includes(term.toLowerCase())),
  chat: async (question: string): Promise<MockChatResponse> => { await delay(900); const supported = /risk|retention|operations|handoff|document|project/i.test(question); return supported ? { answer: 'Across the available local sources, the clearest themes are consistent operational handoffs and explicit lifecycle decisions for working documents. This is a demo response from the isolated frontend mock service, not a verified Ollama answer.', citations: evidence, insufficientEvidence: false } : { answer: 'Insufficient evidence. The available mock sources do not contain enough relevant material to answer that question confidently.', citations: [], insufficientEvidence: true } },
}
function delay(ms: number) { return new Promise((resolve) => setTimeout(resolve, ms)) }
