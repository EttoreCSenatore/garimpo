import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import type { Product } from '../types'
import { formatPrice, getImageUrl, installmentsLabel, safeHttpUrl } from '../lib'

interface Props {
  product: Product
  onClose: () => void
}

export default function ProductDetail({ product, onClose }: Props) {
  const [active, setActive] = useState(0)
  const [failed, setFailed] = useState<Set<number>>(new Set())
  const images = product.images ?? []
  const current = getImageUrl(images[active])
  const productUrl = safeHttpUrl(product.url)
  const isAvailable = product.available && product.status === 'active'
  const installments = installmentsLabel(product)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={product.name}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[92vh] overflow-y-auto relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          aria-label="Fechar"
          className="absolute top-3 right-3 z-10 p-1.5 rounded-full bg-white/90 hover:bg-slate-100 text-slate-500"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="grid md:grid-cols-2 gap-6 p-5">
          {/* Gallery */}
          <div className="flex flex-col gap-3">
            <div className="aspect-square bg-slate-50 rounded-xl overflow-hidden flex items-center justify-center">
              {current && !failed.has(active) ? (
                <img
                  src={current}
                  alt={product.name}
                  className="w-full h-full object-contain"
                  onError={() => setFailed(new Set(failed).add(active))}
                />
              ) : (
                <span className="text-sm text-slate-400">Imagem indisponível</span>
              )}
            </div>
            {images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto">
                {images.map((src, i) => (
                  <button
                    key={src}
                    onClick={() => setActive(i)}
                    aria-label={`Foto ${i + 1}`}
                    className={`w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden border-2 bg-slate-50 ${
                      i === active ? 'border-indigo-500' : 'border-transparent hover:border-slate-300'
                    }`}
                  >
                    <img src={getImageUrl(src)} alt="" className="w-full h-full object-contain" loading="lazy" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Info */}
          <div className="flex flex-col gap-3 min-w-0">
            {product.breadcrumbs?.length > 0 && (
              <p className="text-xs text-slate-400">{product.breadcrumbs.join(' › ')}</p>
            )}
            {product.brand && (
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{product.brand}</span>
            )}
            <h2 className="text-xl font-semibold text-slate-800 leading-snug pr-8">{product.name}</h2>

            <div>
              <span className="text-2xl font-bold text-emerald-600">
                {product.price != null ? formatPrice(product.price) : 'Preço indisponível'}
              </span>
              {installments && <p className="text-sm text-slate-500">ou {installments}</p>}
              {product.price_boleto != null && product.price_boleto !== product.price && (
                <p className="text-sm text-slate-500">
                  À vista: <span className="font-medium text-slate-700">{formatPrice(product.price_boleto)}</span>
                </p>
              )}
            </div>

            <span
              className={`self-start text-xs font-medium px-2 py-0.5 rounded-full border ${
                isAvailable
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-red-50 text-red-600 border-red-200'
              }`}
            >
              {isAvailable ? 'Em estoque' : 'Indisponível'}
            </span>

            {product.sizes?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1.5">Tamanhos disponíveis</p>
                <div className="flex flex-wrap gap-1.5">
                  {product.sizes.map((s) => (
                    <span key={s} className="min-w-9 text-center text-sm border border-slate-200 rounded-md px-2 py-1">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {product.description && (
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-1">Descrição</p>
                <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{product.description}</p>
              </div>
            )}

            <div className="mt-auto pt-2 flex flex-col gap-1">
              {productUrl && (
                <a
                  href={productUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-center bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-xl px-4 py-2.5"
                >
                  Ver na loja
                </a>
              )}
              <p className="text-xs text-slate-400 text-center">
                {product.codigo && <>SKU {product.codigo} · </>}
                Atualizado em {new Date(product.scraped_at).toLocaleDateString('pt-BR')} — confirme preço e estoque na loja.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
