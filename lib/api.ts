export type DocumentRecord = {
  id: string
  filename: string
  content_type?: string
  size?: number
  status: 'indexed' | 'processing' | 'failed' | 'duplicate'
  created_at?: string
  pages?: number
  error?: string
  owner_id?: string
  organization_id?: string
}

export type AgentResearchStep = {
  step: number
  sub_goal: string
  tool: string
  evidence_gathered: number
  sources: string[]
}

export type AgentResearchResponse = {
  goal: string
  status: string
  support_level?: 'fully_supported' | 'partially_supported' | 'unsupported'
  missing_information?: string | null
  duration_ms: number
  plan_queries: string[]
  steps_executed: AgentResearchStep[]
  total_evidence_passages: number
  citations: Citation[]
  numerical_derivations?: Array<{
    type: string
    inputs: string
    result: string
    derivation: string
  }>
  executive_brief: string
  safety_profile: {
    air_gapped: boolean
    external_network_calls: number
    tools_permitted: string[]
    destructive_operations_blocked: boolean
  }
}

export type BenchmarkTestCase = {
  id: string
  type: string
  query: string
  expected_docs: string[]
  expected_facts: string[]
  bm25_baseline: {
    latency_ms: number
    hits_count: number
    retrieved_docs: string[]
    retrieval_recall: number
    retrieval_precision: number
    can_synthesize_cross_doc: boolean
  }
  privora_rag: {
    latency_avg_ms: number
    latency_median_ms: number
    answer: string
    support_level: string
    missing_information: string | null
    citations_count: number
    citation_sources: string[]
    answer_correctness: number
    answer_completeness: number
    hallucination_rate: number
    citation_precision: number
    citation_groundedness: number
    vram_used_mb: number
  }
}

export type BenchmarkReport = {
  suite_name: string
  evaluation_timestamp: string
  hardware_profile: {
    os: string
    cpu: string
    ram_total_gb: number
    gpu: string
    gpu_vram_total_mb: number
    peak_vram_used_mb: number
    vram_headroom_mb: number
    local_model: string
    ollama_version: string
  }
  corpus: {
    documents: Array<{
      filename: string
      format: string
      pages_or_sections: number
      ingestion_latency_ms: number
      coverage: string
    }>
    total_documents: number
    total_passages_indexed: number
  }
  summary_metrics: {
    total_test_cases: number
    overall_answer_correctness_pct: number
    overall_answer_completeness_pct: number
    overall_hallucination_rate_pct: number
    overall_citation_precision_pct: number
    overall_citation_groundedness_pct: number
    average_rag_latency_ms: number
    median_rag_latency_ms: number
    average_bm25_latency_ms: number
    bm25_speedup_factor: string
    rag_accuracy_advantage: string
  }
  test_cases: BenchmarkTestCase[]
}

export type VisualQAResponse = {
  document_id: string
  filename: string
  page_number: number
  question: string
  answer: string
  model: string
  duration_ms: number
  preview_url: string
}

export type Citation = { document_id: string; filename: string; page?: number; section?: string; excerpt: string }
export type ChatResponse = {
  answer: string
  citations: Citation[]
  insufficient_evidence: boolean
  support_level?: 'fully_supported' | 'partially_supported' | 'unsupported'
  missing_information?: string | null
}

export type DocumentPassage = {
  id: number
  page?: number
  section?: string
  text: string
}

export type DocumentPassagesResponse = {
  document_id: string
  filename: string
  pages?: number
  size?: number
  created_at?: string
  status: string
  passages: DocumentPassage[]
}

export type ContradictionFinding = {
  id: string
  type: string
  severity: 'high' | 'medium' | 'low'
  classification: string
  topic: string
  title: string
  description: string
  source_a: {
    document_id: string
    filename: string
    location: string
    excerpt: string
    claimed_value: string
  }
  source_b: {
    document_id: string
    filename: string
    location: string
    excerpt: string
    claimed_value: string
  }
  status: string
}

export type ContradictionsResponse = {
  status: string
  message?: string
  documents_analyzed: string[]
  findings_count: number
  findings: ContradictionFinding[]
}

export type DocumentComparisonResponse = {
  status: string
  document_a: { id: string; filename: string; passages: number }
  document_b: { id: string; filename: string; passages: number }
  aligned_topics: {
    topic: string
    status: 'aligned' | 'conflicting' | 'only_in_document_a' | 'only_in_document_b'
    doc_a?: { value: string; location: string; excerpt: string } | null
    doc_b?: { value: string; location: string; excerpt: string } | null
  }[]
  conflict_count: number
}

export type PrivacyAuditResponse = {
  status: 'verified' | 'warning'
  deployment_mode: string
  model_endpoint: {
    url: string
    is_loopback: boolean
    provider: string
  }
  storage: {
    data_directory: string
    documents_directory: string
    database_file: string
    is_local_filesystem: boolean
  }
  network_audit: {
    active_sockets_inspected: number
    outbound_wan_sockets: number
    is_airgap_ready: boolean
  }
  external_cloud_apis: {
    openai_configured: boolean
    anthropic_configured: boolean
    google_ai_configured: boolean
    azure_ai_configured: boolean
  }
  verified_checks: {
    check: string
    passed: boolean
    evidence: string
  }[]
  known_limitations: string[]
}

export type NumericColumnStats = {
  column: string
  column_ref: string
  cell_range: string
  count: number
  total: number
  mean: number
  min: number
  max: number
}

export type TextColumnStats = {
  column: string
  column_ref: string
  count: number
  distinct_count: number
  sample_values: string[]
}

export type TabularSheetInfo = {
  sheet_name: string
  total_rows: number
  total_columns: number
  headers: string[]
  numeric_columns: NumericColumnStats[]
  text_columns: TextColumnStats[]
}

export type TabularAnalyticsResponse = {
  filename: string
  format: string
  total_sheets: number
  sheets: TabularSheetInfo[]
}

export type SecurityStatusResponse = {
  deployment_mode: 'local' | 'server'
  warnings: string[]
  rate_limiting_enabled: boolean
  session_token_hashing: boolean
  timing_mitigation_active: boolean
  cookie_authentication: boolean
  cookie_httponly: boolean
  cookie_samesite: string
  cookie_secure: boolean
  csrf_protection_active: boolean
}

export type UserRecord = {
  id: string
  email: string
  full_name: string
  role: string
  organization_id: string
  organization_name: string
  organization_slug: string
}

export type AuthResponse = {
  access_token?: string
  token_type?: string
  user: UserRecord
  csrf_token?: string
  mode: 'local' | 'server'
}

export type ModelMetadata = {
  name: string
  tag: string
  label: string
  download_size?: string
  ram_required?: string
  is_default?: boolean
  installed?: boolean
}

export type ModelsResponse = {
  connected: boolean
  active_model: string
  installed: string[]
  available: string[]
  installedModels: ModelMetadata[]
  recommended: ModelMetadata[]
  recommendedModels: ModelMetadata[]
}

export type OnboardingResponse = {
  completed: boolean
  deployment_mode: string
  ollama: {
    connected: boolean
    status: 'connected' | 'unavailable' | string
    url: string
    installed_models: string[]
    available_models: string[]
  }
  installedModels: ModelMetadata[]
  recommended_models: ModelMetadata[]
  recommended: ModelMetadata[]
  offline_evidence_mode_available: boolean
  data_directory?: string
}

export const DEFAULT_RECOMMENDED_MODELS: ModelMetadata[] = [
  {
    name: 'qwen2.5:7b',
    tag: 'qwen2.5:7b',
    label: 'Qwen 2.5 (7B) - Recommended Balanced',
    download_size: '~4.7 GB',
    ram_required: '8 GB+ RAM / VRAM',
    is_default: true,
    installed: false,
  },
  {
    name: 'qwen2.5:3b',
    tag: 'qwen2.5:3b',
    label: 'Qwen 2.5 (3B) - Lightweight',
    download_size: '~2.0 GB',
    ram_required: '4 GB RAM',
    is_default: false,
    installed: false,
  },
  {
    name: 'llama3.2:3b',
    tag: 'llama3.2:3b',
    label: 'Llama 3.2 (3B) - Fast Edge',
    download_size: '~2.0 GB',
    ram_required: '4 GB RAM',
    is_default: false,
    installed: false,
  },
  {
    name: 'qwen2.5:14b',
    tag: 'qwen2.5:14b',
    label: 'Qwen 2.5 (14B) - Enterprise High-Accuracy',
    download_size: '~9.0 GB',
    ram_required: '16 GB+ RAM / VRAM',
    is_default: false,
    installed: false,
  },
]

export function normalizeModelMetadata(raw: unknown, defaultInstalled = false): ModelMetadata {
  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    return {
      name: trimmed,
      tag: trimmed,
      label: trimmed,
      download_size: undefined,
      ram_required: undefined,
      is_default: false,
      installed: defaultInstalled,
    }
  }
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>
    const name = String(obj.name || obj.tag || obj.model || '').trim() || 'unknown'
    const tag = String(obj.tag || obj.name || obj.model || name).trim() || name
    const label = String(obj.label || obj.name || obj.tag || tag).trim() || tag
    return {
      name,
      tag,
      label,
      download_size: typeof obj.download_size === 'string' ? obj.download_size : undefined,
      ram_required: typeof obj.ram_required === 'string' ? obj.ram_required : undefined,
      is_default: Boolean(obj.is_default),
      installed: typeof obj.installed === 'boolean' ? obj.installed : defaultInstalled,
    }
  }
  return {
    name: 'unknown',
    tag: 'unknown',
    label: 'unknown',
    is_default: false,
    installed: defaultInstalled,
  }
}

export function deduplicateModels(models: ModelMetadata[]): ModelMetadata[] {
  const seen = new Set<string>()
  const result: ModelMetadata[] = []
  for (const m of models) {
    const key = (m.tag || m.name).toLowerCase().trim()
    if (!key || key === 'unknown' || seen.has(key)) continue
    seen.add(key)
    result.push(m)
  }
  return result
}

function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '')
  }
  if (typeof window !== 'undefined') {
    if (window.location.port === '3000' || window.location.port === '5173') {
      return `${window.location.protocol}//${window.location.hostname}:8000`
    }
    if (window.location.protocol === 'file:') {
      return 'http://127.0.0.1:8000'
    }
    return ''
  }
  return 'http://127.0.0.1:8000'
}

/**
 * SECURITY ARCHITECTURE - SESSION & CSRF MANAGEMENT
 * Privora uses server-managed HttpOnly, SameSite=Lax session cookies (privora_session)
 * for authenticated sessions, eliminating XSS token theft vectors.
 * For state-changing operations (POST, PUT, DELETE, PATCH), a Double-Submit CSRF cookie
 * (privora_csrf) is paired with an X-CSRF-Token request header and trusted Origin validation.
 */

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const matches = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'))
  return matches ? decodeURIComponent(matches[1]) : null
}

let inMemoryCsrfToken: string | null = null

export function getCsrfToken(): string | null {
  return getCookie('privora_csrf') || inMemoryCsrfToken
}

export function setCsrfToken(token: string | null): void {
  inMemoryCsrfToken = token
}

/**
 * Legacy bearer token fallback for CLI tools and test environments.
 * Primary browser authentication relies on HttpOnly cookies.
 */
export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('privora_token')
}

export function setToken(token: string | null): void {
  if (typeof window === 'undefined') return
  if (token) {
    localStorage.setItem('privora_token', token)
  } else {
    localStorage.removeItem('privora_token')
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)

  // Attach legacy Authorization header if present
  const token = getToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  // Attach X-CSRF-Token header on state-changing requests
  const method = (init?.method ?? 'GET').toUpperCase()
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrf = getCsrfToken()
    if (csrf && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrf)
    }
  }

  const base = getApiBase()
  try {
    const response = await fetch(`${base}${path}`, {
      ...init,
      credentials: 'include',
      headers,
      signal: init?.signal ?? AbortSignal.timeout(10000),
    })

    const contentType = response.headers.get('content-type') ?? ''
    const body = contentType.includes('application/json') ? await response.json() : await response.text()
    if (!response.ok) {
      const detail = typeof body === 'object' && body && 'detail' in body ? String(body.detail) : `Request failed (${response.status})`
      throw new Error(detail)
    }
    return body as T
  } catch (err) {
    if (err instanceof TypeError && (err.message === 'Failed to fetch' || err.message.includes('fetch'))) {
      throw new Error('Cannot connect to Privora local backend server. Please verify the backend engine is running on http://127.0.0.1:8000.')
    }
    if (err instanceof DOMException && err.name === 'TimeoutError') {
      throw new Error('Request to Privora local backend timed out. The server may be busy or processing a large document.')
    }
    throw err
  }
}

export const api = {
  health: () => request<{ status: string; version?: string; mode?: string }>('/api/health'),
  ollama: () => request<{ status: string; model?: string }>('/api/health/ollama'),
  authMode: () => request<{ mode: 'local' | 'server' }>('/api/auth/mode'),
  csrf: async () => {
    const result = await request<{ csrf_token: string }>('/api/auth/csrf')
    if (result?.csrf_token) {
      setCsrfToken(result.csrf_token)
    }
    return result
  },
  login: async (email: string, password: string) => {
    const result = await request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (result.csrf_token) {
      setCsrfToken(result.csrf_token)
    }
    return result
  },
  register: async (payload: { email: string; password: string; full_name: string; organization_name?: string }) => {
    const result = await request<AuthResponse>('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (result.csrf_token) {
      setCsrfToken(result.csrf_token)
    }
    return result
  },
  logout: async () => {
    try {
      return await request<{ logged_out: boolean }>('/api/auth/logout', { method: 'POST' })
    } finally {
      setCsrfToken(null)
    }
  },
  me: () => request<{ user: UserRecord; mode: 'local' | 'server' }>('/api/auth/me'),
  documents: async () => {
    const result = await request<{ documents: DocumentRecord[] }>('/api/documents')
    return result.documents ?? []
  },
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<DocumentRecord>('/api/documents', { method: 'POST', body: form, signal: AbortSignal.timeout(60000) })
  },
  remove: (id: string) => request<{ deleted: boolean }>(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  documentPassages: (id: string) =>
    request<DocumentPassagesResponse>(`/api/documents/${encodeURIComponent(id)}/passages`),
  securityStatus: () => request<SecurityStatusResponse>('/api/system/security-status'),
  chat: (message: string, options?: { model?: string; temperature?: number; top_k?: number }) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, ...options }),
      signal: AbortSignal.timeout(120000),
    }),
  evidence: (term = '') => request<Citation[]>(`/api/evidence${term ? `?q=${encodeURIComponent(term)}` : ''}`),
  getOnboarding: async (): Promise<OnboardingResponse> => {
    try {
      const data = await request<{
        completed?: boolean
        deployment_mode?: string
        ollama?: {
          status?: string
          connected?: boolean
          url?: string
          installed_models?: Array<string | Record<string, unknown>>
          available_models?: Array<string | Record<string, unknown>>
        }
        recommended_models?: Array<string | Record<string, unknown>>
        offline_evidence_mode_available?: boolean
        data_directory?: string
      }>('/api/system/onboarding')

      const rawInstalled = data.ollama?.installed_models || data.ollama?.available_models || []
      const installedModels = deduplicateModels(rawInstalled.map((m) => normalizeModelMetadata(m, true)))
      const rawRecommended = (data.recommended_models && data.recommended_models.length > 0)
        ? data.recommended_models
        : DEFAULT_RECOMMENDED_MODELS
      const recommendedModels = deduplicateModels(rawRecommended.map((m) => normalizeModelMetadata(m, false)))

      const isConnected = data.ollama?.status === 'connected' || Boolean(data.ollama?.connected) || installedModels.length > 0

      return {
        completed: Boolean(data.completed),
        deployment_mode: data.deployment_mode || 'local',
        ollama: {
          connected: isConnected,
          status: isConnected ? 'connected' : 'unavailable',
          url: data.ollama?.url || 'http://127.0.0.1:11434',
          installed_models: installedModels.map((m) => m.tag),
          available_models: installedModels.map((m) => m.tag),
        },
        installedModels,
        recommended_models: recommendedModels,
        recommended: recommendedModels,
        offline_evidence_mode_available: Boolean(data.offline_evidence_mode_available ?? true),
        data_directory: data.data_directory,
      }
    } catch {
      return {
        completed: true,
        deployment_mode: 'local',
        ollama: {
          connected: false,
          status: 'unavailable',
          url: 'http://127.0.0.1:11434',
          installed_models: [],
          available_models: [],
        },
        installedModels: [],
        recommended_models: DEFAULT_RECOMMENDED_MODELS,
        recommended: DEFAULT_RECOMMENDED_MODELS,
        offline_evidence_mode_available: true,
      }
    }
  },
  completeOnboarding: (payload: { completed: boolean; selected_model?: string; workspace_name?: string }) =>
    request<{ status: string; onboarding_completed: boolean }>('/api/system/onboarding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getModels: async (): Promise<ModelsResponse> => {
    try {
      const data = await request<{
        connected?: boolean
        installed?: Array<string | Record<string, unknown>>
        available?: Array<string | Record<string, unknown>>
        recommended?: Array<string | Record<string, unknown>>
        active_model?: string
      }>('/api/system/models')

      const rawInstalled = data.installed || data.available || []
      const installedModels = deduplicateModels(rawInstalled.map((m) => normalizeModelMetadata(m, true)))
      const rawRecommended = (data.recommended && data.recommended.length > 0)
        ? data.recommended
        : DEFAULT_RECOMMENDED_MODELS
      const recommendedModels = deduplicateModels(rawRecommended.map((m) => normalizeModelMetadata(m, false)))

      const installedTags = new Set(installedModels.map((m) => m.tag.toLowerCase()))
      for (const r of recommendedModels) {
        if (installedTags.has(r.tag.toLowerCase()) || installedTags.has(r.name.toLowerCase())) {
          r.installed = true
        }
      }

      const installedStringList = installedModels.map((m) => m.tag)

      return {
        connected: Boolean(data.connected ?? (installedModels.length > 0)),
        active_model: data.active_model || 'qwen2.5:7b',
        installed: installedStringList,
        available: installedStringList,
        installedModels,
        recommended: recommendedModels,
        recommendedModels,
      }
    } catch {
      return {
        connected: false,
        active_model: 'qwen2.5:7b',
        installed: [],
        available: [],
        installedModels: [],
        recommended: DEFAULT_RECOMMENDED_MODELS,
        recommendedModels: DEFAULT_RECOMMENDED_MODELS,
      }
    }
  },
  getDiagnostics: () =>
    request<any>('/api/system/diagnostics'),
  getWorkspaces: () =>
    request<{ workspaces: any[] }>('/api/workspaces'),
  contradictions: (options?: { workspace_id?: string; topic?: string; document_ids?: string[] }) =>
    request<ContradictionsResponse>('/api/analysis/contradictions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {}),
    }),
  compareDocuments: (docIdA: string, docIdB: string) =>
    request<DocumentComparisonResponse>('/api/analysis/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id_a: docIdA, document_id_b: docIdB }),
    }),
  privacyAudit: () =>
    request<PrivacyAuditResponse>('/api/system/privacy-audit'),
  tabularAnalytics: (documentId: string) =>
    request<TabularAnalyticsResponse>(`/api/documents/${documentId}/analytics`),
  agentResearch: (goal: string, model?: string) =>
    request<AgentResearchResponse>('/api/agent/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, model }),
    }),
  getBenchmark: () =>
    request<BenchmarkReport>('/api/benchmark'),
  runBenchmark: () =>
    request<BenchmarkReport>('/api/benchmark/run', { method: 'POST' }),
  visualQA: (documentId: string, pageNumber: number, question: string) =>
    request<VisualQAResponse>(`/api/documents/${documentId}/visual-qa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_number: pageNumber, question }),
    }),
}
