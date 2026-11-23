import type { ChatApiResponse, Deal, Facets, Product, WatchView } from './types'

export async function sendChatMessage(
  message: string,
  sessionId: string,
): Promise<ChatApiResponse> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Erro na API ${res.status}: ${text}`)
  }

  return res.json() as Promise<ChatApiResponse>
}

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) throw new Error(`Erro na API ${res.status}`)
  return res.json() as Promise<T>
}

export interface CatalogQuery {
  q?: string
  brand?: string
  size?: string
  min_price?: string
  max_price?: string
  in_stock: boolean
  sort: string
  offset: number
  limit: number
}

export function fetchCatalog(query: CatalogQuery) {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== '') params.set(k, String(v))
  })
  return getJson<{ items: Product[]; total: number }>(`/api/catalog?${params}`)
}

export const fetchFacets = () => getJson<Facets>('/api/facets')
export const fetchDeals = () => getJson<{ deals: Deal[] }>('/api/deals')

// Alerts: no accounts. The browser keeps a random id that is the only key to its watches.
export function watcherId(): string {
  try {
    let id = localStorage.getItem('garimpo.watcher')
    if (!id) {
      id = (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, '').slice(0, 48)
      localStorage.setItem('garimpo.watcher', id)
    }
    return id
  } catch {
    return 'session' + crypto.randomUUID().replace(/-/g, '')
  }
}

const watchHeaders = () => ({ 'Content-Type': 'application/json', 'X-Watcher-Id': watcherId() })

export const fetchAlertsConfig = () => getJson<{ enabled: boolean; channels: string[] }>('/api/alerts/config')
export const fetchWatches = () => getJson<{ watches: WatchView[] }>('/api/watches', { headers: watchHeaders() })
export const createWatch = (body: {
  product_id: number
  size?: string | null
  target_price?: number | null
  channel: string
  destination: string
}) =>
  getJson<WatchView>('/api/watches', { method: 'POST', headers: watchHeaders(), body: JSON.stringify(body) })
export async function deleteWatch(id: number) {
  const res = await fetch(`/api/watches/${id}`, { method: 'DELETE', headers: watchHeaders() })
  if (!res.ok) throw new Error(`Erro na API ${res.status}`)
}
