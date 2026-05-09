import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Anchor, CaptureMode } from './CodeEditor'

type Props = {
  content: string
  anchors: Anchor[]
  onCapture: (anchor: Anchor, mode: CaptureMode) => void
}

type MdNode = {
  position?: {
    start?: { line: number }
    end?: { line: number }
  }
}

function lineAttrs(node?: MdNode): Record<string, string> {
  const s = node?.position?.start?.line
  const e = node?.position?.end?.line
  if (!s) return {}
  return {
    'data-source-line-start': String(s),
    'data-source-line-end': String(e ?? s),
  }
}

export function MarkdownViewer({ content, anchors, onCapture }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const onCaptureRef = useRef(onCapture)
  useEffect(() => {
    onCaptureRef.current = onCapture
  }, [onCapture])

  // @ asks AI · # saves a comment — anchored to the source-line range of
  // the rendered block under the user's selection (or cursor).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mode: CaptureMode | null =
        e.key === '@' ? 'ai' : e.key === '#' ? 'comment' : null
      if (!mode) return
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (tag === 'textarea' || tag === 'input') return
      const within =
        hostRef.current?.contains(document.activeElement) ?? false
      const sel = window.getSelection()
      const inHost =
        sel?.anchorNode && hostRef.current?.contains(sel.anchorNode)
      if (!within && !inHost) return

      // Find the nearest ancestor that carries source-line metadata.
      let el: Element | null =
        (sel?.anchorNode as Element | null) ?? null
      if (el && el.nodeType === Node.TEXT_NODE) el = el.parentElement
      while (el && !el.hasAttribute?.('data-source-line-start')) {
        el = el.parentElement
      }
      if (!el || !hostRef.current?.contains(el)) {
        // Fallback: pick the topmost block in view.
        el = hostRef.current?.querySelector(
          '[data-source-line-start]',
        ) as Element | null
      }
      if (!el) return
      const start = parseInt(
        el.getAttribute('data-source-line-start') || '1',
        10,
      )
      const end = parseInt(
        el.getAttribute('data-source-line-end') || String(start),
        10,
      )
      e.preventDefault()
      onCaptureRef.current({ startLine: start, endLine: end }, mode)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const anchoredLines = new Set<number>()
  for (const a of anchors) {
    for (let line = a.startLine; line <= a.endLine; line++) {
      anchoredLines.add(line)
    }
  }

  const isAnchored = (node?: MdNode): boolean => {
    const s = node?.position?.start?.line
    const e = node?.position?.end?.line
    if (!s) return false
    for (let line = s; line <= (e ?? s); line++) {
      if (anchoredLines.has(line)) return true
    }
    return false
  }

  const blockClass = (node?: MdNode, base = ''): string =>
    isAnchored(node)
      ? `${base} relative pl-3 -ml-3 border-l-2 border-accent bg-accent/5`
      : base

  return (
    <div
      ref={hostRef}
      tabIndex={0}
      className="h-full overflow-auto outline-none"
    >
      <div className="max-w-[78ch] mx-auto px-8 py-8 leading-[1.7] text-[14px] text-fg">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ node, ...p }) => (
              <h1
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'mt-6 mb-4 text-[24px] font-bold tracking-tight text-accent',
                )}
                {...p}
              />
            ),
            h2: ({ node, ...p }) => (
              <h2
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'mt-8 mb-3 text-[18px] font-semibold tracking-tight text-fg border-b border-border pb-1',
                )}
                {...p}
              />
            ),
            h3: ({ node, ...p }) => (
              <h3
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'mt-5 mb-2 text-[15px] font-semibold text-fg',
                )}
                {...p}
              />
            ),
            h4: ({ node, ...p }) => (
              <h4
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'mt-4 mb-2 text-[13.5px] font-semibold text-fg-dim uppercase tracking-[0.1em]',
                )}
                {...p}
              />
            ),
            p: ({ node, ...p }) => (
              <p
                {...lineAttrs(node)}
                className={blockClass(node, 'my-3')}
                {...p}
              />
            ),
            ul: ({ node, ...p }) => (
              <ul
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'my-3 list-disc pl-6 marker:text-fg-mute',
                )}
                {...p}
              />
            ),
            ol: ({ node, ...p }) => (
              <ol
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'my-3 list-decimal pl-6 marker:text-fg-mute',
                )}
                {...p}
              />
            ),
            li: ({ node, ...p }) => (
              <li {...lineAttrs(node)} className="my-1" {...p} />
            ),
            blockquote: ({ node, ...p }) => (
              <blockquote
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'my-4 border-l-2 border-accent pl-4 text-fg-dim italic',
                )}
                {...p}
              />
            ),
            hr: ({ node, ...p }) => (
              <hr
                {...lineAttrs(node)}
                className="my-6 border-0 border-t border-border"
                {...p}
              />
            ),
            a: ({ node: _n, ...p }) => (
              <a
                className="text-accent underline underline-offset-2 hover:opacity-80"
                target="_blank"
                rel="noreferrer"
                {...p}
              />
            ),
            code: ({ inline, node: _n, className, children, ...p }: {
              inline?: boolean
              node?: unknown
              className?: string
              children?: React.ReactNode
            }) =>
              inline ? (
                <code
                  className="px-1 py-0.5 bg-bg-elevated border border-border text-[12.5px] text-accent"
                  {...p}
                >
                  {children}
                </code>
              ) : (
                <code className={`${className ?? ''} font-mono`} {...p}>
                  {children}
                </code>
              ),
            pre: ({ node, ...p }) => (
              <pre
                {...lineAttrs(node)}
                className={blockClass(
                  node,
                  'my-4 p-3 bg-bg-elevated border border-border overflow-x-auto text-[12.5px] leading-[1.55]',
                )}
                {...p}
              />
            ),
            table: ({ node: _n, ...p }) => (
              <div className="my-4 overflow-x-auto">
                <table
                  className="w-full border-collapse text-[13px]"
                  {...p}
                />
              </div>
            ),
            th: ({ node: _n, ...p }) => (
              <th
                className="text-left px-2 py-1 border-b-2 border-border-strong font-semibold uppercase tracking-[0.05em] text-[11px] text-fg-dim"
                {...p}
              />
            ),
            td: ({ node: _n, ...p }) => (
              <td
                className="px-2 py-1 border-b border-border align-top"
                {...p}
              />
            ),
            img: ({ node: _n, ...p }) => (
              <img className="my-4 max-w-full" {...p} />
            ),
            strong: ({ node: _n, ...p }) => (
              <strong className="text-fg font-semibold" {...p} />
            ),
            em: ({ node: _n, ...p }) => <em className="italic" {...p} />,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}
