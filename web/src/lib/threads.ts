export type Role = 'user' | 'assistant'
export type Message = { role: Role; content: string }
export type ThreadStatus = 'streaming' | 'done' | 'error'

export type Thread = {
  id: string
  file: string
  language: string
  anchor: { startLine: number; endLine: number }
  messages: Message[]
  status: ThreadStatus
  error?: string
  model?: string
}

export type ThreadAction =
  | {
      type: 'START'
      id: string
      file: string
      language: string
      anchor: { startLine: number; endLine: number }
      question: string
    }
  | { type: 'FOLLOWUP'; id: string; question: string }
  | { type: 'START_INFO'; id: string; model: string }
  | { type: 'TOKEN'; id: string; text: string }
  | { type: 'ERROR'; id: string; error: string }
  | { type: 'DONE'; id: string }
  | { type: 'REMOVE'; id: string }

export function threadsReducer(state: Thread[], action: ThreadAction): Thread[] {
  switch (action.type) {
    case 'START':
      return [
        {
          id: action.id,
          file: action.file,
          language: action.language,
          anchor: action.anchor,
          messages: [
            { role: 'user', content: action.question },
            { role: 'assistant', content: '' },
          ],
          status: 'streaming',
        },
        ...state,
      ]
    case 'FOLLOWUP':
      return state.map((t) =>
        t.id === action.id
          ? {
              ...t,
              status: 'streaming',
              error: undefined,
              messages: [
                ...t.messages,
                { role: 'user', content: action.question },
                { role: 'assistant', content: '' },
              ],
            }
          : t,
      )
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
