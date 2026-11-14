import type { Product } from './types'

export function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—'
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

/** Returns the URL only if it is plain http(s); blocks javascript:, data: and other schemes. */
export function safeHttpUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : undefined
  } catch {
    return undefined
  }
}

// Keep in sync with IMAGE_PROXY_ALLOWED_HOSTS on the API.
const PROXIED_HOSTS = ['www.tivolli.com.br']

/** Shop images go through the API's SSRF-safe proxy (same origin, cacheable); others load directly. */
export function getImageUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  const absolute = safeHttpUrl(url.startsWith('//') ? `https:${url}` : url)
  if (!absolute) return undefined
  const isShopHost = PROXIED_HOSTS.includes(new URL(absolute).hostname)
  return isShopHost ? `/api/image-proxy?url=${encodeURIComponent(absolute)}` : absolute
}

export function installmentsLabel(p: Product): string | null {
  const i = p.installments
  if (!i || !i.count || i.count < 2) return null
  return `${i.count}x de ${formatPrice(i.value)}${i.interest_free ? ' sem juros' : ''}`
}
