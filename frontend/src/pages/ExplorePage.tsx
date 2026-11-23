import { useEffect, useState } from 'react'
import { fetchCatalog, fetchFacets } from '../api'
import ProductCard from '../components/ProductCard'
import type { Facets, Product } from '../types'

const PAGE = 24
const SORTS = [
  { id: 'relevance', label: 'Relevância' },
  { id: 'price_asc', label: 'Menor preço' },
  { id: 'price_desc', label: 'Maior preço' },
  { id: 'popular', label: 'Mais vistos' },
  { id: 'newest', label: 'Mais novos' },
  { id: 'name', label: 'Nome (A–Z)' },
]

const field =
  'text-sm bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100'

export default function ExplorePage() {
  const [facets, setFacets] = useState<Facets | null>(null)
  const [q, setQ] = useState('')
  const [brand, setBrand] = useState('')
  const [size, setSize] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [inStock, setInStock] = useState(true)
  const [sort, setSort] = useState('relevance')
  const [items, setItems] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchFacets().then(setFacets).catch(() => {})
  }, [])

  // Any filter change restarts from the first page (the text box is debounced).
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      setLoading(true)
      setError(false)
      fetchCatalog({ q, brand, size, min_price: minPrice, max_price: maxPrice, in_stock: inStock, sort, offset: 0, limit: PAGE })
        .then((r) => {
          if (cancelled) return
          setItems(r.items)
          setTotal(r.total)
        })
        .catch(() => !cancelled && setError(true))
        .finally(() => !cancelled && setLoading(false))
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [q, brand, size, minPrice, maxPrice, inStock, sort])

  const loadMore = () => {
    setLoading(true)
    fetchCatalog({ q, brand, size, min_price: minPrice, max_price: maxPrice, in_stock: inStock, sort, offset: items.length, limit: PAGE })
      .then((r) => {
        setItems((prev) => [...prev, ...r.items])
        setTotal(r.total)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  const clear = () => {
    setQ('')
    setBrand('')
    setSize('')
    setMinPrice('')
    setMaxPrice('')
    setInStock(true)
    setSort('relevance')
  }

  return (
    <div className="h-full overflow-y-auto px-4">
      <div className="max-w-5xl mx-auto py-6">
        <h1 className="text-lg font-semibold text-slate-800 mb-3">Explorar o catálogo</h1>
        <div className="flex flex-wrap items-end gap-2 mb-4" role="search">
          <input
            className={`${field} flex-1 min-w-48`}
            placeholder="Buscar por nome, marca…"
            aria-label="Buscar"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select className={field} aria-label="Marca" value={brand} onChange={(e) => setBrand(e.target.value)}>
            <option value="">Todas as marcas</option>
            {facets?.brands.map((b) => (
              <option key={b.brand} value={b.brand}>
                {b.brand} ({b.count})
              </option>
            ))}
          </select>
          <select className={field} aria-label="Tamanho" value={size} onChange={(e) => setSize(e.target.value)}>
            <option value="">Qualquer tamanho</option>
            {facets?.sizes.map((s) => (
              <option key={s.size} value={s.size}>
                {s.size} ({s.count})
              </option>
            ))}
          </select>
          <input
            className={`${field} w-24`}
            inputMode="decimal"
            placeholder="Mín. R$"
            aria-label="Preço mínimo"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value.replace(/[^0-9.]/g, ''))}
          />
          <input
            className={`${field} w-24`}
            inputMode="decimal"
            placeholder="Máx. R$"
            aria-label="Preço máximo"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value.replace(/[^0-9.]/g, ''))}
          />
          <select className={field} aria-label="Ordenar por" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-slate-600">
            <input type="checkbox" checked={inStock} onChange={(e) => setInStock(e.target.checked)} />
            Só em estoque
          </label>
          <button onClick={clear} className="text-sm text-slate-500 hover:text-indigo-600 underline">
            Limpar
          </button>
        </div>

        <p className="text-xs text-slate-500 mb-3" aria-live="polite">
          {error ? 'Não foi possível carregar o catálogo.' : loading && items.length === 0 ? 'Carregando…' : `${total} produto${total === 1 ? '' : 's'}`}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pb-6">
          {items.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
        {items.length < total && (
          <div className="text-center pb-8">
            <button
              onClick={loadMore}
              disabled={loading}
              className="text-sm bg-white border border-slate-200 rounded-full px-5 py-2 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50"
            >
              {loading ? 'Carregando…' : 'Carregar mais'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
