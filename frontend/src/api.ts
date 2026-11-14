import type { ChatApiResponse } from './types'

export async function sendChatMessage(
  message: string,
  sessionId: string,
): Promise<ChatApiResponse> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Erro na API ${res.status}: ${text}`)
  }

  return res.json() as Promise<ChatApiResponse>
}
