import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Trash2 } from 'lucide-react'

import { sendChatMessage } from '../api'
import type { ChatMessage } from '../types'
import ChatBubble from '../components/ChatBubble'
import TypingIndicator from '../components/TypingIndicator'

const SESSION_ID = crypto.randomUUID()

// Follow-ups that act on the products the last answer showed.
const FOLLOW_UPS = [
  { label: 'Comparar os 3 primeiros', text: 'compare os 3 primeiros' },
  { label: 'Qual o mais barato?', text: 'qual o mais barato?' },
  { label: 'Histórico de preço', text: 'mostre o histórico de preço' },
]

const SUGGESTIONS = [
  'quero um tênis',
  'chuteiras nike',
  'tênis feminino número 38',
  'tênis de corrida',
  'tênis adidas até 500',
  'raquetes yonex',
]

function Welcome({ onSuggest }: { onSuggest: (s: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-6 px-4 pb-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg">
          <span className="text-white text-2xl font-bold">G</span>
        </div>
        <h2 className="text-xl font-semibold text-slate-800">Garimpo · Busca Inteligente</h2>
        <p className="text-sm text-slate-500 max-w-sm">
          Pergunte o que quiser sobre nossos produtos esportivos. Informe gênero e
          número do calçado que eu encontro o produto ideal para você!
        </p>
      </div>

      <div className="flex flex-wrap gap-2 justify-center max-w-md">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="text-xs bg-white border border-slate-200 text-slate-600 hover:border-indigo-300
                       hover:text-indigo-600 rounded-full px-3 py-1.5 transition-colors duration-150"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Fetch last_refresh from health endpoint
  useEffect(() => {
    fetch('/api/')
      .then((r) => r.json())
      .then((data) => {
        if (data.last_refresh) {
          setLastUpdated(
            new Intl.DateTimeFormat('pt-BR', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            }).format(new Date(data.last_refresh)),
          )
        }
      })
      .catch(() => {})
  }, [])

  // Scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, isLoading])

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: trimmed,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const data = await sendChatMessage(trimmed, SESSION_ID)

      const botMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'bot',
        text: data.reply,
        products: data.products,
        filtersApplied: data.filters_applied,
        comparison: data.comparison,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, botMsg])
    } catch {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'bot',
        text: 'Ops! Algo deu errado ao buscar produtos. Verifique se o backend está rodando e tente novamente.',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const clearChat = () => {
    setMessages([])
    inputRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-slate-200 bg-white/80 backdrop-blur-sm px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <span className="text-white text-sm font-bold">G</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-900">Garimpo · Busca Inteligente</h1>
              {lastUpdated && (
                <p className="text-[10px] text-slate-400">Catálogo atualizado em {lastUpdated}</p>
              )}
            </div>
          </div>

          {messages.length > 0 && (
            <button
              onClick={clearChat}
              title="Limpar conversa"
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-500 transition-colors p-1.5 rounded-lg hover:bg-red-50"
            >
              <Trash2 size={14} />
              Limpar
            </button>
          )}
        </div>
      </header>

      {/* Chat area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto chat-scroll px-4"
      >
        <div className="max-w-3xl mx-auto w-full py-6 flex flex-col gap-4">
          {messages.length === 0 ? (
            <Welcome onSuggest={(s) => sendMessage(s)} />
          ) : (
            messages.map((msg) => <ChatBubble key={msg.id} message={msg} />)
          )}

          {!isLoading && (messages[messages.length - 1]?.products?.length ?? 0) > 0 && (
            <div className="ml-11 flex flex-wrap gap-2">
              {FOLLOW_UPS.map((f) => (
                <button
                  key={f.text}
                  onClick={() => sendMessage(f.text)}
                  className="text-xs bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-50
                             rounded-full px-3 py-1.5 transition-colors duration-150"
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}

          {isLoading && <TypingIndicator />}
        </div>
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-3">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 bg-white border border-slate-200 rounded-2xl shadow-sm
                          focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100
                          transition-all duration-150 px-4 py-2.5">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Busque por produtos… ex: 'tênis feminino nº 38' ou 'chuteiras nike'"
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm text-slate-800 placeholder:text-slate-400
                         focus:outline-none max-h-32 leading-relaxed"
              style={{ fieldSizing: 'content' } as React.CSSProperties}
              disabled={isLoading}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading}
              className="flex-shrink-0 w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center
                         text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-colors duration-150"
              aria-label="Enviar mensagem"
            >
              <ArrowUp size={15} strokeWidth={2.5} />
            </button>
          </div>
          <p className="text-center text-[10px] text-slate-400 mt-1.5">
            Pressione Enter para enviar · Shift+Enter para quebra de linha
          </p>
        </div>
      </div>
    </div>
  )
}
