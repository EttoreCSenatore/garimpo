import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

interface Release {
  version: string
  date: string
  title: string
  items: { kind: 'new' | 'improvement' | 'fix' | 'security'; text: string }[]
}

const KIND_LABEL: Record<string, string> = {
  new: 'Novo',
  improvement: 'Melhoria',
  fix: 'Correção',
  security: 'Segurança',
}

export default function WhatsNew({ onClose }: { onClose: () => void }) {
  const [releases, setReleases] = useState<Release[] | null>(null)

  useEffect(() => {
    fetch('/api/releases?lang=pt-br')
      .then((r) => r.json())
      .then((d: { releases: Release[] }) => setReleases(d.releases))
      .catch(() => setReleases([]))
  }, [])

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
      aria-label="Novidades"
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto p-5 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          aria-label="Fechar"
          className="absolute top-3 right-3 p-1.5 rounded-full hover:bg-slate-100 text-slate-500"
        >
          <X className="w-5 h-5" />
        </button>
        <h2 className="text-lg font-semibold text-slate-800 mb-3">Novidades</h2>
        {releases === null && <p className="text-sm text-slate-400">Carregando…</p>}
        {releases?.length === 0 && <p className="text-sm text-slate-400">Não foi possível carregar o histórico.</p>}
        <div className="flex flex-col gap-5">
          {releases?.map((r) => (
            <section key={r.version}>
              <h3 className="text-sm font-semibold text-slate-800">
                v{r.version} <span className="font-normal text-slate-400">· {r.date}</span>
              </h3>
              <p className="text-sm text-slate-600 mb-1.5">{r.title}</p>
              <ul className="text-sm text-slate-600 flex flex-col gap-1">
                {r.items.map((i, idx) => (
                  <li key={idx}>
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-indigo-600 mr-1.5">
                      {KIND_LABEL[i.kind] ?? i.kind}
                    </span>
                    {i.text}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
