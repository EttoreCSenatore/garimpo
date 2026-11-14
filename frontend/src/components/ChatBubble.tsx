import type { ReactNode } from 'react'
import type { ChatMessage } from '../types'
import ProductCard from './ProductCard'

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
