import { useState } from 'react'
import type { Product } from '../types'

interface ProductCardProps {
  product: Product
}

function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—'
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
  }).format(value)
}

/** Returns the URL only if it is plain http(s); blocks javascript:, data: and other schemes. */
function safeHttpUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : undefined
  } catch {
    return undefined
  }
}

function getImageUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  const absolute = safeHttpUrl(url.startsWith('//') ? `https:${url}` : url)
  if (!absolute) return undefined
  const host = new URL(absolute).hostname
  const isShopHost = /(^|\.)(tivolli\.com\.br|tivollisports\.com\.br)$/.test(host)
  return isShopHost ? `/api/image-proxy?url=${encodeURIComponent(absolute)}` : absolute
}

export default function ProductCard({ product }: ProductCardProps) {
  const [imgError, setImgError] = useState(false)
  const mainImage = product.images?.[0]
  const displayImage = getImageUrl(mainImage)
  const isAvailable = product.available && product.status === 'active'
  const productUrl = safeHttpUrl(product.url)

  return (
    <a
      href={productUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex flex-col bg-white rounded-2xl border border-slate-100 overflow-hidden
                 hover:shadow-lg hover:border-slate-200 transition-all duration-200 cursor-pointer"
    >
      {/* Image */}
      <div className="relative aspect-square bg-slate-50 overflow-hidden">
        {displayImage && !imgError ? (
          <img
            src={displayImage}
            alt={product.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-300">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-16 h-16"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
        )}

        {/* Stock badge */}
        <span
          className={`absolute top-2 right-2 flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full
            ${isAvailable
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-red-50 text-red-600 border border-red-200'
            }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${isAvailable ? 'bg-emerald-500' : 'bg-red-500'}`}
          />
          {isAvailable ? 'Em estoque' : 'Indisponível'}
        </span>
      </div>

      {/* Info */}
      <div className="flex flex-col flex-1 p-3 gap-1">
        {product.brand && (
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {product.brand}
          </span>
        )}

        <p className="text-sm font-semibold text-slate-800 line-clamp-2 leading-snug">
          {product.name}
        </p>

        {/* Price */}
        <div className="mt-auto pt-2">
          {product.price != null ? (
            <span className="text-base font-bold text-emerald-600">
              {formatPrice(product.price)}
            </span>
          ) : (
            <span className="text-sm text-slate-400 italic">Preço indisponível</span>
          )}

          {product.price_boleto != null && product.price_boleto !== product.price && (
            <p className="text-xs text-slate-400 mt-0.5">
              À vista:{' '}
              <span className="font-medium text-slate-600">
                {formatPrice(product.price_boleto)}
              </span>
            </p>
          )}
        </div>
      </div>
    </a>
  )
}
