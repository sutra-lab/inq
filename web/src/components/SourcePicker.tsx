import { useEffect, useRef, useState } from 'react'
import {
  addDriveSource,
  fetchSources,
  googleAuthPopup,
  type SourceInfo,
} from '../api'

type Props = {
  currentSource: string
  onSourceChange: (id: string) => void
}

export function SourcePicker({ currentSource, onSourceChange }: Props) {
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [open, setOpen] = useState(false)
  const [showDialog, setShowDialog] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  const refresh = async () => {
    try {
      const r = await fetchSources()
      setSources(r.sources)
    } catch {
      // server might be a moment from booting; retry on next mount cycle
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  // close the dropdown on outside click
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onClick)
    return () => window.removeEventListener('mousedown', onClick)
  }, [open])

  const current = sources.find((s) => s.id === currentSource)
  const display = current?.label ?? currentSource

  return (
    <div ref={wrapRef} className="relative w-full">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 h-9 border-b border-border text-[11px] hover:bg-bg-elevated"
      >
        <span className="text-fg-mute uppercase tracking-[0.2em] text-[10px] shrink-0">
          source
        </span>
        <span className="text-fg truncate flex-1 text-left">{display}</span>
        <span className="text-fg-mute text-[9px]">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 z-30 border border-border-strong bg-bg-elevated">
          {sources.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                onSourceChange(s.id)
                setOpen(false)
              }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12px] hover:bg-bg-active text-left ${
                s.id === currentSource ? 'text-accent' : 'text-fg'
              }`}
            >
              <span className="w-3 inline-block">
                {s.id === currentSource ? '✓' : ''}
              </span>
              <span className="truncate">{s.label}</span>
            </button>
          ))}
          <div className="border-t border-border" />
          <button
            onClick={() => {
              setOpen(false)
              setShowDialog(true)
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-[12px] hover:bg-bg-active text-left text-accent"
          >
            <span className="w-3 inline-block">+</span>
            <span>open google drive folder…</span>
          </button>
        </div>
      )}

      {showDialog && (
        <DriveDialog
          onClose={() => setShowDialog(false)}
          onAdded={async (info) => {
            await refresh()
            onSourceChange(info.id)
            setShowDialog(false)
          }}
        />
      )}
    </div>
  )
}

function DriveDialog({
  onClose,
  onAdded,
}: {
  onClose: () => void
  onAdded: (info: SourceInfo) => void
}) {
  const [folder, setFolder] = useState('')
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState<'idle' | 'auth' | 'adding'>('idle')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const submit = async () => {
    const trimmed = folder.trim()
    if (!trimmed) return
    setBusy(true)
    setError(null)
    setStep('adding')
    try {
      let mismatch = false
      try {
        const info = await addDriveSource(trimmed)
        onAdded(info)
        return
      } catch (e: unknown) {
        const code = (e as { code?: string })?.code
        if (code === 'google_auth_required') {
          // first-time auth
        } else if (code === 'google_account_mismatch') {
          mismatch = true
        } else {
          throw e
        }
      }
      setStep('auth')
      // For mismatch, force the account picker so the user can switch
      // to the account that owns / has access to this folder.
      await googleAuthPopup(mismatch ? { prompt: 'select_account' } : undefined)
      setStep('adding')
      const info = await addDriveSource(trimmed)
      onAdded(info)
    } catch (e: unknown) {
      setError(String(e))
      setStep('idle')
    } finally {
      setBusy(false)
    }
  }

  const stepLabel =
    step === 'auth'
      ? 'waiting for google sign-in…'
      : step === 'adding'
        ? 'opening folder…'
        : ''

  return (
    <div
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      className="fixed inset-0 z-50 bg-bg/85 backdrop-blur-sm flex items-start justify-center pt-[15vh]"
    >
      <div className="w-[480px] max-w-[90vw] border border-border-strong bg-bg-elevated">
        <header className="flex items-center gap-2 px-3 h-9 border-b border-border text-[11px]">
          <span className="text-accent uppercase tracking-[0.2em] font-semibold">
            open drive folder
          </span>
          <button
            onClick={onClose}
            className="ml-auto text-fg-mute hover:text-fg text-sm leading-none"
            title="close"
          >
            ×
          </button>
        </header>
        <div className="p-3 space-y-3">
          <p className="text-[12px] text-fg-dim leading-relaxed">
            paste a google drive folder URL or its id. inq will request{' '}
            <span className="text-accent">drive.readonly</span> access on first
            use; a popup will open.
          </p>
          <input
            ref={inputRef}
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submit()
              if (e.key === 'Escape') onClose()
            }}
            placeholder="https://drive.google.com/drive/folders/…"
            className="w-full bg-bg border border-border px-2 py-1.5 text-[12px] text-fg outline-none focus:border-accent"
            disabled={busy}
          />
          {stepLabel && (
            <div className="text-[11px] text-fg-mute">{stepLabel}</div>
          )}
          {error && (
            <div className="text-[11px] text-danger break-words">{error}</div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={onClose}
              disabled={busy}
              className="px-3 py-1 text-[11px] text-fg-dim hover:text-fg uppercase tracking-[0.15em]"
            >
              cancel
            </button>
            <button
              onClick={submit}
              disabled={busy || !folder.trim()}
              className="px-3 py-1 text-[11px] text-bg bg-accent hover:opacity-90 disabled:opacity-40 uppercase tracking-[0.15em] font-semibold"
            >
              {busy ? '…' : 'open'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
