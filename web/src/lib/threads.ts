export type Role = 'user' | 'assistant'
export type Message = { role: Role; content: string }
export type ThreadStatus = 'streaming' | 'done' | 'error'
export type ThreadMode = 'ai' | 'comment'

export type Thread = {
  id: string
  file: string
  language: string
  kind: 'text' | 'pdf'
  mode: ThreadMode
  anchor: { startLine: number; endLine: number }
  messages: Message[]
  status: ThreadStatus
  error?: string
  model?: string
}

export type ThreadAction =
  | { type: 'LOAD'; threads: Thread[] }
  | {
      type: 'START'
      id: string
      file: string
      language: string
      kind: 'text' | 'pdf'
      mode: ThreadMode
      anchor: { startLine: number; endLine: number }
      body: string
    }
  | { type: 'FOLLOWUP'; id: string; body: string }
  | { type: 'START_INFO'; id: string; model: string }
  | { type: 'TOKEN'; id: string; text: string }
  | { type: 'ERROR'; id: string; error: string }
  | { type: 'DONE'; id: string }
  | { type: 'REMOVE'; id: string }

export function threadsReducer(state: Thread[], action: ThreadAction): Thread[] {
  switch (action.type) {
    case 'LOAD':
      return action.threads
    case 'START':
      return [
        {
          id: action.id,
          file: action.file,
          language: action.language,
          kind: action.kind,
          mode: action.mode,
          anchor: action.anchor,
          messages:
            action.mode === 'ai'
              ? [
                  { role: 'user', content: action.body },
                  { role: 'assistant', content: '' },
                ]
              : [{ role: 'user', content: action.body }],
          status: action.mode === 'ai' ? 'streaming' : 'done',
        },
        ...state,
      ]
    case 'FOLLOWUP':
      return state.map((t) => {
        if (t.id !== action.id) return t
        if (t.mode === 'ai') {
          return {
            ...t,
            status: 'streaming',
            error: undefined,
            messages: [
              ...t.messages,
              { role: 'user', content: action.body },
              { role: 'assistant', content: '' },
            ],
          }
        }
        return {
          ...t,
          status: 'done',
          error: undefined,
          messages: [...t.messages, { role: 'user', content: action.body }],
        }
      })
    case 'TOKEN':
      return state.map((t) => {
        if (t.id !== action.id) return t
        const msgs = [...t.messages]
        const last = msgs[msgs.length - 1]
        if (last && last.role === 'assistant') {
          msgs[msgs.length - 1] = { ...last, content: last.content + action.text }
        }
        return { ...t, messages: msgs }
      })
    case 'START_INFO':
      return state.map((t) => (t.id === action.id ? { ...t, model: action.model } : t))
    case 'DONE':
      return state.map((t) =>
        t.id === action.id && t.status === 'streaming' ? { ...t, status: 'done' } : t,
      )
    case 'ERROR':
      return state.map((t) =>
        t.id === action.id ? { ...t, status: 'error', error: action.error } : t,
      )
    case 'REMOVE':
      return state.filter((t) => t.id !== action.id)
  }
}

export function priorHistory(thread: Thread): Message[] {
  // For follow-ups: send all completed user/assistant pairs as history.
  // Drop the trailing empty assistant if present.
  const last = thread.messages[thread.messages.length - 1]
  if (last && last.role === 'assistant' && last.content === '') {
    return thread.messages.slice(0, -1)
  }
  return thread.messages
}
