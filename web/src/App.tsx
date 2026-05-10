import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { FileTree } from './components/FileTree'
import { CodeEditor, type Anchor, type CaptureMode } from './components/CodeEditor'
import { AskBar } from './components/AskBar'
import { ResponsePanel } from './components/ResponsePanel'
import {
  deleteThread,
  fetchFile,
  fetchThreads,
  rawUrl,
  saveThread,
  type FileData,
} from './api'
import { MarkdownViewer } from './components/MarkdownViewer'
import { PdfViewer } from './components/PdfViewer'
import { SourcePicker } from './components/SourcePicker'
import { ask } from './lib/sse'
import { priorHistory, threadsReducer, type Thread } from './lib/threads'
import { useTheme, type Theme } from './lib/theme'

export default function App() {
  const [currentSource, setCurrentSource] = useState<string>('local')
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [fileData, setFileData] = useState<FileData | null>(null)
  const [loadingFile, setLoadingFile] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)

  const [pendingAnchor, setPendingAnchor] = useState<Anchor | null>(null)
  const [pendingMode, setPendingMode] = useState<CaptureMode>('ai')
  const [threads, dispatch] = useReducer(threadsReducer, [] as Thread[])
  const threadsRef = useRef(threads)
  threadsRef.current = threads
  const currentSourceRef = useRef(currentSource)
  currentSourceRef.current = currentSource

  const [theme, , toggleTheme] = useTheme()
  const [sourceLabel, setSourceLabel] = useState<string>('')

  // Load persisted threads when the source changes (and on mount).
  useEffect(() => {
    let cancelled = false
    setSelectedPath(null)
    setFileData(null)
    fetchThreads(currentSource)
      .then((res) => {
        if (cancelled) return
        setSourceLabel(res.source)
        const cleaned = res.threads.map((t) =>
          t.status === 'streaming' ? { ...t, status: 'error' as const, error: 'interrupted' } : t,
        )
        dispatch({ type: 'LOAD', threads: cleaned })
        lastPersisted.current = new Map()
      })
      .catch((e) => {
        console.warn('[inq] could not load persisted threads:', e)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSource])

  // Persist threads when they reach a terminal state (done / error). Track the
  // last persisted status per id so we don't fire on every TOKEN.
  const lastPersisted = useRef<Map<string, string>>(new Map())
  useEffect(() => {
    for (const t of threads) {
      const prev = lastPersisted.current.get(t.id)
      const isTerminal = t.status === 'done' || t.status === 'error'
      if (isTerminal && prev !== t.status) {
        lastPersisted.current.set(t.id, t.status)
        saveThread(t, currentSourceRef.current).catch((e) =>
          console.warn('[inq] saveThread failed:', e),
        )
      }
    }
  }, [threads])

  // Load file content when selection changes
  useEffect(() => {
    if (!selectedPath) {
      setFileData(null)
      setFileError(null)
      return
    }
    let cancelled = false
    setLoadingFile(true)
    setFileError(null)
    setPendingAnchor(null)
    fetchFile(selectedPath, currentSource)
      .then((d) => {
        if (!cancelled) setFileData(d)
      })
      .catch((e) => {
        if (!cancelled) {
          setFileData(null)
          setFileError(String(e))
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingFile(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedPath, currentSource])

  // Anchors for the currently open file (used to draw line markers)
  const anchorsForCurrentFile = useMemo<Anchor[]>(() => {
    if (!selectedPath) return []
    return threads.filter((t) => t.file === selectedPath).map((t) => t.anchor)
  }, [threads, selectedPath])

  const anchorPagesForCurrentFile = useMemo<number[]>(() => {
    if (!selectedPath) return []
    return threads
      .filter((t) => t.file === selectedPath && t.kind === 'pdf')
      .map((t) => t.anchor.startLine)
  }, [threads, selectedPath])

  const currentKind: 'text' | 'pdf' =
    fileData?.kind === 'pdf' ? 'pdf' : 'text'

  const isMarkdown =
    fileData?.kind === 'text' && fileData.language === 'markdown'
  const [mdView, setMdView] = useState<'rendered' | 'source'>('rendered')
  // Reset to rendered each time a new markdown file opens.
  useEffect(() => {
    if (isMarkdown) setMdView('rendered')
  }, [selectedPath, isMarkdown])

  const handleCapture = useCallback((anchor: Anchor, mode: CaptureMode) => {
    setPendingAnchor(anchor)
    setPendingMode(mode)
  }, [])

  const handleSubmit = useCallback(
    (body: string) => {
      if (!pendingAnchor || !fileData || !selectedPath) return
      const id = crypto.randomUUID()
      const file = selectedPath
      const kind: 'text' | 'pdf' = fileData.kind === 'pdf' ? 'pdf' : 'text'
      const language = fileData.kind === 'text' ? fileData.language : kind
      const mode = pendingMode
      dispatch({
        type: 'START',
        id,
        file,
        language,
        kind,
        mode,
        anchor: pendingAnchor,
        body,
      })
      setPendingAnchor(null)
      if (mode === 'ai') {
        void ask(
          {
            question: body,
            file,
            anchor: pendingAnchor,
            context_lines: 20,
            full_file: false,
            history: [],
          },
          {
            onStart: ({ model }) => dispatch({ type: 'START_INFO', id, model }),
            onToken: (text) => dispatch({ type: 'TOKEN', id, text }),
            onError: (error) => dispatch({ type: 'ERROR', id, error }),
            onDone: () => dispatch({ type: 'DONE', id }),
          },
          undefined,
          currentSource,
        )
      }
      // mode === 'comment': nothing else to do — reducer set status='done',
      // and the persistence effect will save it on the next render.
    },
    [pendingAnchor, pendingMode, fileData, selectedPath, currentSource],
  )

  const handleFollowup = useCallback((id: string, body: string) => {
    const t = threadsRef.current.find((x) => x.id === id)
    if (!t) return
    dispatch({ type: 'FOLLOWUP', id, body })
    if (t.mode !== 'ai') return
    const history = priorHistory(t)
    void ask(
      {
        question: body,
        file: t.file,
        anchor: t.anchor,
        context_lines: 20,
        full_file: false,
        history,
      },
      {
        onToken: (text) => dispatch({ type: 'TOKEN', id, text }),
        onError: (error) => dispatch({ type: 'ERROR', id, error }),
        onDone: () => dispatch({ type: 'DONE', id }),
      },
      undefined,
      currentSourceRef.current,
    )
  }, [])

  const handleRemove = useCallback((id: string) => {
    dispatch({ type: 'REMOVE', id })
    lastPersisted.current.delete(id)
    deleteThread(id, currentSourceRef.current).catch((e) =>
      console.warn('[inq] deleteThread failed:', e),
    )
  }, [])

  // Save the latest in-memory snapshot of a thread to disk, after React has
  // applied a dispatch. Used for edit/delete operations on individual messages,
  // since neither changes thread.status (so the terminal-status save hook
  // doesn't fire on its own).
  const persistAfterDispatch = useCallback((id: string) => {
    queueMicrotask(() => {
      const t = threadsRef.current.find((x) => x.id === id)
      if (!t) return
      saveThread(t, currentSourceRef.current).catch((e) =>
        console.warn('[inq] saveThread failed:', e),
      )
    })
  }, [])

  const handleEditMessage = useCallback(
    (id: string, index: number, content: string) => {
      dispatch({ type: 'EDIT_MESSAGE', id, index, content })
      persistAfterDispatch(id)
    },
    [persistAfterDispatch],
  )

  const handleDeleteMessage = useCallback(
    (id: string, index: number) => {
      const t = threadsRef.current.find((x) => x.id === id)
      if (!t) return
      // If this is the last remaining message, drop the whole thread —
      // an empty thread is a confusing UI state.
      if (t.messages.length <= 1) {
        handleRemove(id)
        return
      }
      dispatch({ type: 'DELETE_MESSAGE', id, index })
      persistAfterDispatch(id)
    },
    [handleRemove, persistAfterDispatch],
  )

  const handleFocusAnchor = useCallback(
    (file: string, _anchor: Anchor) => {
      if (file !== selectedPath) setSelectedPath(file)
    },
    [selectedPath],
  )

  // Cancel a pending ask with Esc when the bar isn't focused
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && pendingAnchor) {
        const tag = (document.activeElement?.tagName || '').toLowerCase()
        if (tag !== 'textarea' && tag !== 'input') {
          setPendingAnchor(null)
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pendingAnchor])

  return (
    <div className="h-full flex flex-col bg-bg text-fg">
      <TopBar threadCount={threads.length} theme={theme} onToggleTheme={toggleTheme} />
      <div className="flex-1 min-h-0 flex">
      {/* Left: file tree */}
      <aside className="w-64 shrink-0 border-r border-border flex flex-col">
        <SourcePicker
          currentSource={currentSource}
          onSourceChange={setCurrentSource}
        />
        <div className="flex-1 overflow-y-auto">
          <FileTree
            source={currentSource}
            selectedPath={selectedPath}
            onSelect={setSelectedPath}
          />
        </div>
      </aside>

      {/* Center: viewer */}
      <main className="flex-1 min-w-0 flex flex-col">
        <PanelHeader>
          <Label>read</Label>
          <span className="text-fg truncate">
            {fileData?.name ?? selectedPath ?? '—'}
          </span>
          <span className="ml-auto flex items-center gap-3 text-fg-mute">
            {isMarkdown && (
              <button
                onClick={() =>
                  setMdView((v) => (v === 'rendered' ? 'source' : 'rendered'))
                }
                title="toggle rendered / source"
                className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em]"
              >
                <span
                  className={
                    mdView === 'rendered' ? 'text-accent' : 'text-fg-dim'
                  }
                >
                  rendered
                </span>
                <span className="text-fg-mute">/</span>
                <span
                  className={
                    mdView === 'source' ? 'text-accent' : 'text-fg-dim'
                  }
                >
                  source
                </span>
              </button>
            )}
            {fileData && fileData.kind === 'text' && (
              <span>
                {fileData.language} · {formatSize(fileData.size)}
              </span>
            )}
            {fileData && fileData.kind === 'pdf' && (
              <span>
                pdf · {fileData.page_count}p · {formatSize(fileData.size)}
              </span>
            )}
          </span>
        </PanelHeader>
        <div className="flex-1 min-h-0 flex flex-col">
          <div className="flex-1 min-h-0 overflow-hidden">
            {loadingFile && <div className="px-4 py-3 text-fg-dim">loading…</div>}
            {fileError && (
              <div className="px-4 py-3 text-danger break-words">{fileError}</div>
            )}
            {(fileData?.kind === 'binary' || fileData?.kind === 'skipped') && (
              <div className="px-4 py-3 text-warn">
                file skipped: {fileData.skipped ?? fileData.kind}
              </div>
            )}
            {fileData?.kind === 'text' && isMarkdown && mdView === 'rendered' && (
              <MarkdownViewer
                content={fileData.content}
                anchors={anchorsForCurrentFile}
                onCapture={handleCapture}
              />
            )}
            {fileData?.kind === 'text' &&
              !(isMarkdown && mdView === 'rendered') && (
                <CodeEditor
                  value={fileData.content}
                  language={fileData.language}
                  anchors={anchorsForCurrentFile}
                  theme={theme}
                  onCapture={handleCapture}
                />
              )}
            {fileData?.kind === 'pdf' && selectedPath && (
              <PdfViewer
                url={rawUrl(selectedPath, currentSource)}
                pageCount={fileData.page_count}
                anchorPages={anchorPagesForCurrentFile}
                onCapture={handleCapture}
              />
            )}
            {!selectedPath && !loadingFile && (
              <div className="px-4 py-6 text-fg-dim leading-relaxed">
                <div>open a file from the tree to start reading.</div>
                <div className="mt-2 text-fg-mute">
                  press <span className="text-accent">@</span> on any line to ask.
                </div>
              </div>
            )}
          </div>
          <AskBar
            anchor={pendingAnchor}
            fileKind={currentKind}
            mode={pendingMode}
            onSubmit={handleSubmit}
            onCancel={() => setPendingAnchor(null)}
          />
        </div>
      </main>

      {/* Right: responses */}
      <aside className="w-96 shrink-0 border-l border-border flex flex-col">
        <PanelHeader>
          <Label>ask</Label>
          <span className="text-fg-mute">
            {threads.length === 0
              ? 'no threads yet'
              : `${threads.length} thread${threads.length === 1 ? '' : 's'}`}
          </span>
        </PanelHeader>
        <div className="flex-1 overflow-y-auto">
          <ResponsePanel
            threads={threads}
            source={sourceLabel}
            onFollowup={handleFollowup}
            onRemove={handleRemove}
            onEditMessage={handleEditMessage}
            onDeleteMessage={handleDeleteMessage}
            onFocusAnchor={handleFocusAnchor}
          />
        </div>
      </aside>
      </div>
    </div>
  )
}

function TopBar({
  threadCount,
  theme,
  onToggleTheme,
}: {
  threadCount: number
  theme: Theme
  onToggleTheme: () => void
}) {
  return (
    <header className="flex items-center gap-3 px-4 h-12 border-b border-border-strong bg-bg shrink-0 select-none">
      <span className="text-accent font-bold text-[20px] tracking-[0.22em] leading-none">
        INQ
      </span>
      <span aria-hidden className="w-px h-4 bg-border-strong" />
      <span className="text-fg-mute text-[10px] uppercase tracking-[0.28em]">
        inquiry
      </span>
      <span className="ml-auto flex items-center gap-3 text-[10px] uppercase tracking-[0.2em] text-fg-mute">
        <span>
          <span className="text-fg-dim">{threadCount}</span> threads
        </span>
        <span aria-hidden className="w-px h-3 bg-border" />
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <span aria-hidden className="w-px h-3 bg-border" />
        <span>v0.1</span>
      </span>
    </header>
  )
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      title={`switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      className="flex items-center gap-1.5 hover:text-fg transition-none"
    >
      <span className={theme === 'dark' ? 'text-accent' : ''}>dark</span>
      <span className="text-fg-mute">/</span>
      <span className={theme === 'light' ? 'text-accent' : ''}>light</span>
    </button>
  )
}

function PanelHeader({ children }: { children: React.ReactNode }) {
  return (
    <header className="flex items-baseline gap-2 px-3 h-9 border-b border-border text-[11px] shrink-0">
      {children}
    </header>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span className="text-fg-mute uppercase tracking-[0.2em] text-[10px]">{children}</span>
  )
}

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
