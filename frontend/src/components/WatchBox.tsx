import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { createWatch, deleteWatch, fetchAlertsConfig, fetchWatches } from '../api'
import type { Product, WatchView } from '../types'

function suggestTopic(): string {
  return 'garimpo-' + crypto.randomUUID().replace(/-/g, '').slice(0, 12)
}

function storedTopic(): string {
  try {
    return localStorage.getItem('garimpo.ntfy') || suggestTopic()
  } catch {
    return suggestTopic()
  }
}

/** "Avisar-me": price-drop and restock alerts through ntfy (or an allowed webhook). Hidden when the server has alerts off. */
export default function WatchBox({ product }: { product: Product }) {
  const [channels, setChannels] = useState<string[]>([])
  const [mine, setMine] = useState<WatchView[]>([])
  const [channel, setChannel] = useState('ntfy')
  const [destination, setDestination] = useState(storedTopic)
  const [size, setSize] = useState('')
  const [target, setTarget] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const reload = () =>
    fetchWatches()
      .then((r) => setMine(r.watches.filter((w) => w.product_id === product.id)))
      .catch(() => {})

  useEffect(() => {
    fetchAlertsConfig()
      .then((c) => {
        setChannels(c.enabled ? c.channels : [])
        if (c.enabled) reload()
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.id])

  if (channels.length === 0) return null

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    try {
      await createWatch({
        product_id: product.id,
        size: size || null,
        target_price: target ? Number(target) : null,
        channel,
        destination: destination.trim(),
      })
      if (channel === 'ntfy') {
        try {
          localStorage.setItem('garimpo.ntfy', destination.trim())
        } catch {
          /* private mode: the topic just is not remembered */
        }
      }
      setMessage('Pronto! Você será avisado quando o preço baixar ou o produto voltar ao estoque.')
      reload()
    } catch {
      setMessage('Não foi possível criar o aviso. Confira o destino e tente de novo.')
    } finally {
      setBusy(false)
    }
  }

  const input =
    'text-sm bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-300'

  return (
    <div className="border border-slate-200 rounded-xl p-3 flex flex-col gap-2">
      <p className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
        <Bell className="w-4 h-4" /> Avisar-me
      </p>
      <div className="flex flex-wrap gap-2">
        {channels.length > 1 && (
          <select className={input} aria-label="Canal" value={channel} onChange={(e) => setChannel(e.target.value)}>
            {channels.map((c) => (
              <option key={c} value={c}>
                {c === 'ntfy' ? 'ntfy' : 'Webhook'}
              </option>
            ))}
          </select>
        )}
        <input
          className={`${input} flex-1 min-w-40`}
          aria-label={channel === 'ntfy' ? 'Tópico do ntfy' : 'URL do webhook'}
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        />
      </div>
      {channel === 'ntfy' && (
        <p className="text-xs text-slate-500">
          Instale o app <strong>ntfy</strong> e assine este tópico (guarde-o: quem souber o nome recebe seus avisos).
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {product.sizes?.length > 0 && (
          <select className={input} aria-label="Tamanho" value={size} onChange={(e) => setSize(e.target.value)}>
            <option value="">Qualquer tamanho</option>
            {product.sizes.map((s) => (
              <option key={s} value={s}>
                Tamanho {s}
              </option>
            ))}
          </select>
        )}
        <input
          className={`${input} w-36`}
          inputMode="decimal"
          placeholder="Preço-alvo (R$)"
          aria-label="Preço-alvo"
          value={target}
          onChange={(e) => setTarget(e.target.value.replace(/[^0-9.]/g, ''))}
        />
        <button
          onClick={submit}
          disabled={busy || !destination.trim()}
          className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-1.5 disabled:opacity-50"
        >
          Criar aviso
        </button>
      </div>
      {message && <p className="text-xs text-slate-600">{message}</p>}
      {mine.length > 0 && (
        <ul className="text-xs text-slate-600 flex flex-col gap-1">
          {mine.map((w) => (
            <li key={w.id} className="flex items-center justify-between gap-2">
              <span>
                {w.size ? `Tamanho ${w.size}` : 'Qualquer tamanho'}
                {w.target_price != null && ` · até R$ ${w.target_price}`} · {w.channel} {w.destination}
              </span>
              <button
                onClick={() => deleteWatch(w.id).then(reload)}
                className="text-red-600 hover:underline"
                aria-label="Remover aviso"
              >
                remover
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
