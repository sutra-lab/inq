import { useState } from 'react'
import type { Thread } from '../lib/threads'
import { copyToClipboard, renderAll, renderThread } from '../lib/markdown'

type Props = {
  threads: Thread[]
  source: string
  onFollowup: (id: string, question: string) => void
  onRemove: (id: string) => void
  onFocusAnchor: (file: string, anchor: { startLine: number; endLine: number }) => void
}

export function ResponsePanel({
  threads,
  source,
  onFollowup,
  onRemove,
  onFocusAnchor,
}: Props) {
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
      <ExportAllBar threads={threads} source={source} />
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

function ExportAllBar({ threads, source }: { threads: Thread[]; source: string }) {
  const [copied, setCopied] = useState(false)
  const onCopy = async () => {
    const ok = await copyToClipboard(renderAll(threads, source))
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    }
  }
  return (
    <div className="flex items-center gap-2 px-3 h-7 border-b border-border text-[10px] uppercase tracking-[0.2em] bg-bg">
      <span className="text-fg-mute">{threads.length} thread{threads.length === 1 ? '' : 's'}</span>
      <button
        onClick={onCopy}
        className="ml-auto text-fg-dim hover:text-accent normal-case tracking-normal text-[11px]"
        title="copy all threads as markdown"
      >
        {copied ? 'copied ✓' : 'copy all md'}
      </button>
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
        <span className="text-accent uppercase tracking-[0.2em] font-semibold shrink-0">
          {thread.mode === 'comment' ? '# note' : '@ ask'}
        </span>
        <span className="text-fg-mute">·</span>
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
          <CopyMdButton thread={thread} />
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
            mode={thread.mode}
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
        <FollowupInput
          mode={thread.mode}
          onSubmit={(q) => onFollowup(thread.id, q)}
        />
      )}
    </article>
  )
}

function CopyMdButton({ thread }: { thread: Thread }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={async () => {
        const ok = await copyToClipboard(renderThread(thread))
        if (ok) {
          setCopied(true)
          setTimeout(() => setCopied(false), 1200)
        }
      }}
      className="hover:text-fg text-[10px]"
      title="copy this thread as markdown"
    >
      {copied ? '✓' : 'md'}
    </button>
  )
}

function Message({
  role,
  content,
  mode,
  streaming,
}: {
  role: 'user' | 'assistant'
  content: string
  mode: 'ai' | 'comment'
  streaming: boolean
}) {
  const userSigil = mode === 'comment' ? '#' : '›'
  return (
    <div className="flex gap-2 px-3 py-2 text-[12.5px] leading-[1.55]">
      <span
        className={
          role === 'user'
            ? 'text-accent select-none shrink-0'
            : 'text-fg-mute select-none shrink-0'
        }
      >
        {role === 'user' ? userSigil : '·'}
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

function FollowupInput({
  mode,
  onSubmit,
}: {
  mode: 'ai' | 'comment'
  onSubmit: (q: string) => void
}) {
  const [v, setV] = useState('')
  const sigil = mode === 'comment' ? '#' : '›'
  const placeholder = mode === 'comment' ? 'add another note…' : 'follow up…'
  return (
    <div className="flex items-start gap-2 px-3 py-2 border-t border-border bg-bg-elevated">
      <span className="text-fg-mute select-none pt-1">{sigil}</span>
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
        placeholder={placeholder}
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
