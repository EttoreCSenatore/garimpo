import { useState } from 'react'
import ChatPage from './pages/ChatPage'
import DealsPage from './pages/DealsPage'
import ExplorePage from './pages/ExplorePage'

const TABS = [
  { id: 'chat', label: 'Chat' },
  { id: 'explore', label: 'Explorar' },
  { id: 'deals', label: 'Ofertas' },
] as const

type Tab = (typeof TABS)[number]['id']

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <nav className="flex-shrink-0 bg-white border-b border-slate-200 px-4" aria-label="Seções">
        <div className="max-w-5xl mx-auto flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? 'page' : undefined}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? 'border-indigo-600 text-indigo-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>
      <div className="flex-1 min-h-0 overflow-hidden">
        {tab === 'chat' && <ChatPage />}
        {tab === 'explore' && <ExplorePage />}
        {tab === 'deals' && <DealsPage />}
      </div>
    </div>
  )
}
