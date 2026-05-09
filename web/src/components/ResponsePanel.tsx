import { useState } from 'react'
import type { Thread } from '../lib/threads'

type Props = {
  threads: Thread[]
  onFollowup: (id: string, question: string) => void
  onRemove: (id: string) => void
  onFocusAnchor: (file: string, anchor: { startLine: number; endLine: number }) => void
}

export function ResponsePanel({ threads, onFollowup, onRemove, onFocusAnchor }: Props) {
  if (threads.length === 0) {
    return (
      <div className="px-3 py-3 text-fg-dim leading-relaxed">
        <div>
          press <span className="text-accent">@</span> on a line — or with a range
          selected — to ask a question.
        </div>
        <div className="mt-2 text-fg-mute">
          file context is sent with the question; follow-ups stay in the same thread.
        </div>
      </div>
    )
  }
  return (
    <div className="flex flex-col">
      {threads.map((t) => (
        <ThreadCard
          key={t.id}
          thread={t}
          onFollowup={onFollowup}
          onRemove={onRemove}
          onFocusAnchor={onFocusAnchor}
        />
      ))}
    </div>
  )
}

function ThreadCard({
  thread,
  onFollowup,
  onRemove,
  onFocusAnchor,
}: {
  thread: Thread
  onFollowup: (id: string, question: string) => void
  onRemove: (id: string) => void
  onFocusAnchor: (file: string, anchor: { startLine: number; endLine: number }) => void
}) {
  const rangeLabel =
    thread.kind === 'pdf'
      ? `:p${thread.anchor.startLine}`
      : thread.anchor.startLine === thread.anchor.endLine
        ? `:${thread.anchor.startLine}`
        : `:${thread.anchor.startLine}–${thread.anchor.endLine}`

  return (
    <article className="border-b border-border">
      <header className="flex items-baseline gap-2 px-3 h-7 text-[10px] bg-bg-elevated">
        <button
          onClick={() => onFocusAnchor(thread.file, thread.anchor)}
          className="text-fg hover:text-accent truncate"
          title="jump to anchor"
        >
          {thread.file}
          <span className="text-accent">{rangeLabel}</span>
        </button>
        <span className="ml-auto flex items-center gap-2 text-fg-mute">
          {thread.status === 'streaming' && (
            <span className="text-accent">streaming…</span>
          )}
          {thread.status === 'error' && <span className="text-danger">error</span>}
          <button
            onClick={() => onRemove(thread.id)}
            className="hover:text-fg"
            title="dismiss thread"
          >
            ×
          </button>
        </span>
      </header>

      <div className="divide-y divide-border">
        {thread.messages.map((m, i) => (
          <Message
            key={i}
            role={m.role}
            content={m.content}
            streaming={
              thread.status === 'streaming' &&
              i === thread.messages.length - 1 &&
              m.role === 'assistant'
            }
          />
        ))}
        {thread.error && (
          <div className="px-3 py-2 text-[12px] text-danger break-words">
            {thread.error}
          </div>
        )}
      </div>

      {thread.status !== 'streaming' && (
        <FollowupInput onSubmit={(q) => onFollowup(thread.id, q)} />
      )}
    </article>
  )
}

function Message({
  role,
  content,
  streaming,
}: {
  role: 'user' | 'assistant'
  content: string
  streaming: boolean
}) {
  return (
    <div className="flex gap-2 px-3 py-2 text-[12.5px] leading-[1.55]">
      <span
        className={
          role === 'user'
            ? 'text-accent select-none shrink-0'
            : 'text-fg-mute select-none shrink-0'
        }
      >
        {role === 'user' ? '›' : '·'}
      </span>
      <div className="min-w-0 flex-1 whitespace-pre-wrap break-words text-fg">
        {content}
        {streaming && (
          <span className="inline-block w-[7px] h-[13px] -mb-[2px] ml-[2px] bg-accent align-baseline animate-pulse" />
        )}
      </div>
    </div>
  )
}

function FollowupInput({ onSubmit }: { onSubmit: (q: string) => void }) {
  const [v, setV] = useState('')
  return (
    <div className="flex items-start gap-2 px-3 py-2 border-t border-border bg-bg-elevated">
      <span className="text-fg-mute select-none pt-1">›</span>
      <textarea
        value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            const q = v.trim()
            if (q) {
              onSubmit(q)
              setV('')
            }
          }
        }}
        rows={1}
        placeholder="follow up…"
        className="flex-1 bg-transparent text-fg placeholder:text-fg-mute resize-none outline-none border-0 text-[12.5px] leading-[1.5] py-0.5"
        style={{ minHeight: '20px', maxHeight: '120px' }}
        onInput={(e) => {
          const ta = e.currentTarget
          ta.style.height = 'auto'
          ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
        }}
      />
    </div>
  )
}
