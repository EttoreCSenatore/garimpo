import { useEffect, useState } from 'react'
import { fetchDeals } from '../api'
import ProductCard from '../components/ProductCard'
import { formatPrice } from '../lib'
import type { Deal } from '../types'

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchDeals()
      .then((d) => setDeals(d.deals))
      .catch(() => setError(true))
  }, [])

  return (
    <div className="h-full overflow-y-auto px-4">
      <div className="max-w-5xl mx-auto py-6">
        <h1 className="text-lg font-semibold text-slate-800">Ofertas de verdade</h1>
        <p className="text-sm text-slate-500 mb-4 max-w-2xl">
          Produtos que estão no menor preço que o Garimpo já registrou nos últimos 90 dias, com a queda calculada pelo
          histórico de preços de cada um, não pelo &ldquo;de/por&rdquo; da loja.
        </p>
        {error && <p className="text-sm text-red-600">Não foi possível carregar as ofertas.</p>}
        {deals === null && !error && <p className="text-sm text-slate-400">Carregando…</p>}
        {deals?.length === 0 && (
          <p className="text-sm text-slate-500">
            Ainda não há quedas de preço registradas. O histórico cresce a cada coleta; volte em breve.
          </p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pb-8">
          {deals?.map((d) => (
            <div key={d.product.id} className="flex flex-col gap-1.5">
              <ProductCard product={d.product} />
              <p className="text-xs text-emerald-700 font-medium px-1">
                −{d.discount_pct.toFixed(0)}% · de {formatPrice(d.was)} por {formatPrice(d.now)} · menor preço em {d.days} dias
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
