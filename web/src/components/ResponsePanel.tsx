import { useState } from 'react'
import type { Thread } from '../lib/threads'
import { copyToClipboard, renderAll, renderThread } from '../lib/markdown'

type Props = {
  threads: Thread[]
  source: string
  onFollowup: (id: string, question: string) => void
  onRemove: (id: string) => void
  onEditMessage: (id: string, index: number, content: string) => void
  onDeleteMessage: (id: string, index: number) => void
  onFocusAnchor: (file: string, anchor: { startLine: number; endLine: number }) => void
}

export function ResponsePanel({
  threads,
  source,
  onFollowup,
  onRemove,
  onEditMessage,
  onDeleteMessage,
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
          onEditMessage={onEditMessage}
          onDeleteMessage={onDeleteMessage}
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
  onEditMessage,
  onDeleteMessage,
  onFocusAnchor,
}: {
  thread: Thread
  onFollowup: (id: string, question: string) => void
  onRemove: (id: string) => void
  onEditMessage: (id: string, index: number, content: string) => void
  onDeleteMessage: (id: string, index: number) => void
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
            editable={
              m.role === 'user' &&
              !(thread.status === 'streaming' && i === thread.messages.length - 1)
            }
            onEdit={(content) => onEditMessage(thread.id, i, content)}
            onDelete={() => onDeleteMessage(thread.id, i)}
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
  editable,
  onEdit,
  onDelete,
}: {
  role: 'user' | 'assistant'
  content: string
  mode: 'ai' | 'comment'
  streaming: boolean
  editable: boolean
  onEdit: (content: string) => void
  onDelete: () => void
}) {
  const userSigil = mode === 'comment' ? '#' : '›'
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(content)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const startEdit = () => {
    setDraft(content)
    setEditing(true)
    setConfirmDelete(false)
  }
  const cancelEdit = () => {
    setEditing(false)
    setDraft(content)
  }
  const saveEdit = () => {
    const next = draft.trim()
    if (!next) {
      // empty -> treat as delete
      setEditing(false)
      onDelete()
      return
    }
    if (next !== content) onEdit(next)
    setEditing(false)
  }

  return (
    <div className="group flex gap-2 px-3 py-2 text-[12.5px] leading-[1.55]">
      <span
        className={
          role === 'user'
            ? 'text-accent select-none shrink-0'
            : 'text-fg-mute select-none shrink-0'
        }
      >
        {role === 'user' ? userSigil : '·'}
      </span>
      <div className="min-w-0 flex-1">
        {editing ? (
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                saveEdit()
              } else if (e.key === 'Escape') {
                e.preventDefault()
                cancelEdit()
              } else if (e.key === 'd' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault()
                saveEdit()
              }
            }}
            rows={Math.max(1, draft.split('\n').length)}
            className="w-full bg-bg-elevated border border-accent text-fg resize-none outline-none px-2 py-1 leading-[1.5] text-[12.5px]"
            style={{ minHeight: '24px', maxHeight: '320px' }}
            onInput={(e) => {
              const ta = e.currentTarget
              ta.style.height = 'auto'
              ta.style.height = Math.min(ta.scrollHeight, 320) + 'px'
            }}
          />
        ) : (
          <span className="whitespace-pre-wrap break-words text-fg">
            {content}
            {streaming && (
              <span className="inline-block w-[7px] h-[13px] -mb-[2px] ml-[2px] bg-accent align-baseline animate-pulse" />
            )}
          </span>
        )}
      </div>
      {editable && (
        <div className="shrink-0 flex items-start gap-2 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] uppercase tracking-[0.15em] text-fg-mute pt-[1px]">
          {editing ? (
            <>
              <button
                onClick={saveEdit}
                className="hover:text-accent"
                title="save (enter)"
              >
                save
              </button>
              <button
                onClick={cancelEdit}
                className="hover:text-fg"
                title="cancel (esc)"
              >
                cancel
              </button>
            </>
          ) : confirmDelete ? (
            <>
              <button
                onClick={() => {
                  setConfirmDelete(false)
                  onDelete()
                }}
                className="text-danger hover:opacity-80"
              >
                delete?
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="hover:text-fg"
              >
                no
              </button>
            </>
          ) : (
            <>
              <button onClick={startEdit} className="hover:text-fg" title="edit">
                edit
              </button>
              <button
                onClick={() => setConfirmDelete(true)}
                className="hover:text-danger"
                title="delete"
              >
                ×
              </button>
            </>
          )}
        </div>
      )}
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
