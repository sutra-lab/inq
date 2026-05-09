import { useEffect, useRef, useState } from 'react'
import type { Anchor, CaptureMode } from './CodeEditor'

type Props = {
  anchor: Anchor | null
  fileKind?: 'text' | 'pdf'
  mode: CaptureMode
  onSubmit: (body: string) => void
  onCancel: () => void
}

export function AskBar({ anchor, fileKind = 'text', mode, onSubmit, onCancel }: Props) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (anchor) {
      setValue('')
      inputRef.current?.focus()
    }
  }, [anchor, mode])

  if (!anchor) return null

  const submit = () => {
    const v = value.trim()
    if (!v) return
    onSubmit(v)
    setValue('')
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onCancel()
    } else if (e.key === 'd' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      submit()
    }
  }

  const rangeLabel =
    fileKind === 'pdf'
      ? `page ${anchor.startLine}`
      : anchor.startLine === anchor.endLine
        ? `line ${anchor.startLine}`
        : `lines ${anchor.startLine}–${anchor.endLine}`

  const isComment = mode === 'comment'
  const sigil = isComment ? '#' : '@'
  const verb = isComment ? 'comment' : 'ask'
  const placeholder = isComment
    ? 'leave a note for this region…'
    : 'ask about the highlighted region…'
  const helpRight = isComment
    ? 'enter to save · esc to cancel'
    : 'enter to send · esc to cancel'

  return (
    <div className="border-t border-border bg-bg-elevated">
      <div className="flex items-center gap-2 px-3 h-7 border-b border-border text-[10px]">
        <span className="text-accent uppercase tracking-[0.2em] font-semibold">
          {sigil} {verb}
        </span>
        <span className="text-fg-mute">·</span>
        <span className="text-fg">{rangeLabel}</span>
        <span className="ml-auto text-fg-mute">{helpRight}</span>
      </div>
      <div className="flex items-start gap-2 p-2">
        <span className="text-accent pt-1.5 select-none">{sigil}</span>
        <textarea
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={1}
          className="flex-1 bg-transparent text-fg placeholder:text-fg-mute resize-none outline-none border-0 leading-[1.5] py-1"
          style={{ minHeight: '24px', maxHeight: '160px' }}
          onInput={(e) => {
            const ta = e.currentTarget
            ta.style.height = 'auto'
            ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
          }}
        />
      </div>
    </div>
  )
}
