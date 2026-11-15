import { useEffect, useState } from 'react'
import { formatPrice } from '../lib'

interface Point {
  price: number
  at: string
}

/** Price line over time, drawn from the API's recorded history (no chart library). */
export default function PriceHistory({ productId }: { productId: number }) {
  const [points, setPoints] = useState<Point[] | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/products/${productId}/history?limit=200`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: { history: { price: string | number | null; scraped_at: string }[] }) => {
        if (cancelled) return
        const pts = data.history
          .filter((h) => h.price != null)
          .map((h) => ({ price: Number(h.price), at: h.scraped_at }))
          .reverse()
        setPoints(pts)
      })
      .catch(() => !cancelled && setPoints([]))
    return () => {
      cancelled = true
    }
  }, [productId])

  if (!points) return null
  if (points.length < 2) {
    return <p className="text-xs text-slate-400">Histórico de preço: ainda sem variações registradas.</p>
  }

  const prices = points.map((p) => p.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const span = max - min || 1
  const w = 280
  const h = 64
  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * w
    const y = h - ((p.price - min) / span) * (h - 8) - 4
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  return (
    <div>
      <p className="text-xs font-semibold text-slate-500 mb-1">Histórico de preço</p>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full h-16" role="img" aria-label="Gráfico do histórico de preço">
        <polyline points={coords.join(' ')} fill="none" stroke="#4f46e5" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="text-xs text-slate-500">
        Menor {formatPrice(min)} · maior {formatPrice(max)}
      </p>
    </div>
  )
}
