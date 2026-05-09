export type SSEEvent = { event: string; data: string }

export async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      yield parseBlock(block)
    }
  }
  if (buf.trim()) yield parseBlock(buf)
}

function parseBlock(block: string): SSEEvent {
  let event = 'message'
  const dataLines: string[] = []
  for (const raw of block.split('\n')) {
    if (raw.startsWith('event: ')) event = raw.slice(7).trim()
    else if (raw.startsWith('data: ')) dataLines.push(raw.slice(6))
    else if (raw.startsWith('data:')) dataLines.push(raw.slice(5))
  }
  return { event, data: dataLines.join('\n') }
}

export type AskRequest = {
  question: string
  file: string
  anchor: { startLine: number; endLine: number }
  context_lines?: number
  full_file?: boolean
  history?: { role: 'user' | 'assistant'; content: string }[]
}

export type AskHandlers = {
  onStart?: (info: { model: string }) => void
  onToken?: (text: string) => void
  onUsage?: (u: Record<string, number | null>) => void
  onError?: (msg: string) => void
  onDone?: () => void
}

export async function ask(
  req: AskRequest,
  handlers: AskHandlers,
  signal?: AbortSignal,
  source?: string,
): Promise<void> {
  const url = source ? `/api/ask?source=${encodeURIComponent(source)}` : '/api/ask'
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!res.ok) {
    const text = await res.text()
    handlers.onError?.(`${res.status}: ${text}`)
    handlers.onDone?.()
    return
  }
  if (!res.body) {
    handlers.onError?.('no response body')
    handlers.onDone?.()
    return
  }
  for await (const ev of parseSSE(res.body)) {
    switch (ev.event) {
      case 'start':
        try {
          handlers.onStart?.(JSON.parse(ev.data))
        } catch {
          /* ignore */
        }
        break
      case 'token':
        handlers.onToken?.(ev.data)
        break
      case 'usage':
        try {
          handlers.onUsage?.(JSON.parse(ev.data))
        } catch {
          /* ignore */
        }
        break
      case 'error':
        handlers.onError?.(ev.data)
        break
      case 'done':
        handlers.onDone?.()
        return
    }
  }
  handlers.onDone?.()
}
