import type { ReactNode } from 'react'
import type { ChatMessage } from '../types'
import ProductCard from './ProductCard'
import { formatPrice, installmentsLabel } from '../lib'
import type { Comparison } from '../types'

function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const rows = comparison.rows
  return (
    <div className="ml-11 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-xs text-left">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium"></th>
            {rows.map((r) => (
              <th key={r.id} className="px-3 py-2 font-medium align-top min-w-40">{r.name}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          <tr>
            <td className="px-3 py-2 text-slate-500">Preço</td>
            {rows.map((r) => (
              <td key={r.id} className={`px-3 py-2 font-semibold ${r.cheapest ? 'text-emerald-600' : ''}`}>
                {formatPrice(r.price == null ? null : Number(r.price))}
                {r.cheapest && <span className="ml-1 text-[10px] font-medium">mais barato</span>}
              </td>
            ))}
          </tr>
          <tr>
            <td className="px-3 py-2 text-slate-500">Parcelas</td>
            {rows.map((r) => (
              <td key={r.id} className="px-3 py-2">{installmentsLabel({ installments: r.installments } as never) ?? '—'}</td>
            ))}
          </tr>
          <tr>
            <td className="px-3 py-2 text-slate-500">Tamanhos</td>
            {rows.map((r) => (
              <td key={r.id} className="px-3 py-2">{r.sizes.length ? r.sizes.join(', ') : '—'}</td>
            ))}
          </tr>
          <tr>
            <td className="px-3 py-2 text-slate-500">Estoque</td>
            {rows.map((r) => (
              <td key={r.id} className="px-3 py-2">{r.available ? 'Em estoque' : 'Indisponível'}</td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}

/** Renders the small markdown subset the API uses (**bold**, newlines) as React nodes, never raw HTML. */
function renderRichText(text: string): ReactNode[] {
  return text.split('\n').flatMap((line, lineIndex, lines) => {
    const parts = line.split(/\*\*(.+?)\*\*/g).map((part, i) =>
      i % 2 === 1 ? <strong key={`${lineIndex}-${i}`}>{part}</strong> : part,
    )
    return lineIndex < lines.length - 1 ? [...parts, <br key={`br-${lineIndex}`} />] : parts
  })
}

interface ChatBubbleProps {
  message: ChatMessage
}

export default function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[75%] bg-blue-500 text-white rounded-2xl rounded-tr-sm
                     px-4 py-2.5 text-sm shadow-sm"
        >
          {message.text}
        </div>
      </div>
    )
  }

  // Bot message
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600
                        flex items-center justify-center shadow-sm">
          <span className="text-white text-xs font-bold">AI</span>
        </div>

        {/* Text reply */}
        <div
          className="bg-white border border-slate-100 rounded-2xl rounded-tl-sm
                     px-4 py-3 text-sm text-slate-700 shadow-sm max-w-[80%] leading-relaxed"
        >
          {renderRichText(message.text)}
        </div>
      </div>

      {message.comparison && message.comparison.rows.length > 1 && (
        <ComparisonTable comparison={message.comparison} />
      )}

      {/* Product grid */}
      {message.products && message.products.length > 0 && (
        <div className="ml-11 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {message.products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}
