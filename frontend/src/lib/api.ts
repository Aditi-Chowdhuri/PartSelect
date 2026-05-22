const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8001'

export async function* streamChat(
  messages: Array<{ role: string; content: string }>,
  sessionId: string
): AsyncGenerator<{ type: string; content: string | any[] }> {
  const response = await fetch(`${BACKEND_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, session_id: sessionId }),
  })

  if (!response.ok) {
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After')
      const wait = retryAfter ? ` Please wait ${retryAfter} seconds.` : ' Please wait a moment.'
      throw new Error(`Rate limit reached.${wait} Try again shortly.`)
    }
    let detail = `Backend error: ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }

  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          yield data
        } catch {
          // skip malformed SSE lines
        }
      }
    }
  }
}
