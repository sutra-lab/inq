import { useEffect, useRef, useState } from 'react'
import type { Anchor } from './CodeEditor'

type Props = {
  anchor: Anchor | null
  onSubmit: (question: string) => void
  onCancel: () => void
}

export function AskBar({ anchor, onSubmit, onCancel }: Props) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (anchor) {
      setValue('')
      inputRef.current?.focus()
    }
  }, [anchor])

  if (!anchor) return null

  const submit = () => {
    const q = value.trim()
    if (!q) return
    onSubmit(q)
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
    anchor.startLine === anchor.endLine
      ? `line ${anchor.startLine}`
      : `lines ${anchor.startLine}–${anchor.endLine}`

  return (
    <div className="border-t border-border bg-bg-elevated">
      <div className="flex items-center gap-2 px-3 h-7 border-b border-border text-[10px]">
        <span className="text-accent uppercase tracking-[0.2em] font-semibold">@ ask</span>
        <span className="text-fg-mute">·</span>
        <span className="text-fg">{rangeLabel}</span>
        <span className="ml-auto text-fg-mute">enter to send · esc to cancel</span>
      </div>
      <div className="flex items-start gap-2 p-2">
        <span className="text-accent pt-1.5 select-none">›</span>
        <textarea
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder="ask about the highlighted region…"
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
