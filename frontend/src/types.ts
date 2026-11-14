export interface Product {
  id: number
  slug: string
  url: string
  name: string
  codigo?: string | null
  currency: string
  price?: number | null
  price_boleto?: number | null
  installments?: { count: number; value: number; interest_free: boolean } | null
  sizes: string[]
  available: boolean
  description?: string | null
  images: string[]
  category_id?: number | null
  breadcrumbs: string[]
  brand?: string | null
  status: 'active' | 'out_of_stock' | 'disappeared'
  scraped_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  products?: Product[]
  filtersApplied?: Record<string, unknown>
  timestamp: Date
}

export interface ChatApiResponse {
  reply: string
  filters_applied: Record<string, unknown>
  products: Product[]
}
