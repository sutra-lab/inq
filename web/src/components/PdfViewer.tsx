import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { Anchor } from './CodeEditor'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

type Props = {
  url: string
  pageCount: number
  anchorPages: number[]
  onAsk: (anchor: Anchor) => void
}

export function PdfViewer({ url, pageCount, anchorPages, onAsk }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null)
  const onAskRef = useRef(onAsk)
  useEffect(() => {
    onAskRef.current = onAsk
  }, [onAsk])

  const [doc, setDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [page, setPage] = useState(1)
  const [scale] = useState(1.4)
  const [error, setError] = useState<string | null>(null)

  // Reset to page 1 whenever the file changes (avoids out-of-range pages
  // when switching from a 50-page doc to a 3-page one).
  useEffect(() => {
    setPage(1)
  }, [url])

  // Load the document.
  useEffect(() => {
    let cancelled = false
    setError(null)
    const task = pdfjsLib.getDocument({ url })
    task.promise
      .then((d) => {
        if (cancelled) {
          d.destroy()
          return
        }
        setDoc(d)
      })
      .catch((e) => {
        if (!cancelled) setError(String(e))
      })
    return () => {
      cancelled = true
      // Don't destroy here — the doc-cleanup effect handles it on doc change.
    }
  }, [url])

  // Destroy the doc when it changes or on unmount.
  useEffect(() => {
    return () => {
      doc?.destroy()
    }
  }, [doc])

  // Render the current page.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!doc || !canvas) return
    const target = Math.min(Math.max(1, page), doc.numPages)
    let cancelled = false

    const render = async () => {
      try {
        const p = await doc.getPage(target)
        if (cancelled) return
        const viewport = p.getViewport({ scale })
        const ratio = window.devicePixelRatio || 1
        canvas.width = Math.floor(viewport.width * ratio)
        canvas.height = Math.floor(viewport.height * ratio)
        canvas.style.width = `${Math.floor(viewport.width)}px`
        canvas.style.height = `${Math.floor(viewport.height)}px`
        if (renderTaskRef.current) renderTaskRef.current.cancel()
        const task = p.render({
          canvas,
          viewport,
          transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
        })
        renderTaskRef.current = task
        await task.promise
      } catch (e: unknown) {
        const name = (e as { name?: string })?.name
        if (name !== 'RenderingCancelledException') setError(String(e))
      }
    }
    void render()
    return () => {
      cancelled = true
      if (renderTaskRef.current) renderTaskRef.current.cancel()
    }
  }, [doc, page, scale])

  // @ keybind for PDFs — anchored to the current page.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== '@') return
      const tag = (document.activeElement?.tagName || '').toLowerCase()
      if (tag === 'textarea' || tag === 'input') return
      const within = containerRef.current?.contains(document.activeElement) ?? false
      const focusedSelf = document.activeElement === document.body || within
      if (!focusedSelf) return
      e.preventDefault()
      onAskRef.current({ startLine: page, endLine: page })
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [page])

  const hasMark = anchorPages.includes(page)

  return (
    <div ref={containerRef} className="h-full flex flex-col" tabIndex={0}>
      <div className="flex items-center gap-2 px-3 h-7 border-b border-border text-[10px] uppercase tracking-[0.2em] text-fg-mute shrink-0">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="hover:text-fg disabled:opacity-30"
        >
          ‹ prev
        </button>
        <span className="text-fg-dim normal-case tracking-normal">
          page <span className={hasMark ? 'text-accent' : 'text-fg'}>{page}</span> /{' '}
          {pageCount}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
          disabled={page >= pageCount}
          className="hover:text-fg disabled:opacity-30"
        >
          next ›
        </button>
        <span className="ml-auto normal-case tracking-normal text-fg-mute">
          press <span className="text-accent">@</span> to ask about this page
        </span>
      </div>
      <div className="flex-1 overflow-auto bg-bg-elevated flex items-start justify-center p-6">
        {error ? (
          <div className="text-danger text-[12px]">{error}</div>
        ) : (
          <canvas
            ref={canvasRef}
            className={`bg-white ${hasMark ? 'shadow-[inset_0_0_0_2px_var(--color-accent)]' : ''}`}
          />
        )}
      </div>
    </div>
  )
}
