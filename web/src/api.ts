export type TreeNode = {
  name: string
  path: string
  type: 'dir' | 'file'
  children?: TreeNode[]
}

export type Tree = {
  path: string
  children: TreeNode[]
}

export type FileKind = 'text' | 'pdf' | 'binary' | 'skipped'

export type FileData =
  | {
      path: string
      name?: string
      kind: 'text'
      language: string
      content: string
      size: number
    }
  | {
      path: string
      name?: string
      kind: 'pdf'
      size: number
      page_count: number
    }
  | {
      path: string
      name?: string
      kind: 'binary' | 'skipped'
      size: number
      skipped?: string
    }

export function rawUrl(path: string, source?: string): string {
  const qs = new URLSearchParams({ path })
  if (source) qs.set('source', source)
  return `/api/raw?${qs}`
}

// --- sources --------------------------------------------------------

export type SourceInfo = {
  id: string
  kind: 'local' | 'drive'
  label: string
  default?: boolean
}

export async function fetchSources(): Promise<{ default: string; sources: SourceInfo[] }> {
  const res = await fetch('/api/sources')
  if (!res.ok) throw new Error(`sources ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function addDriveSource(folder: string): Promise<SourceInfo> {
  const res = await fetch('/api/sources/drive', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ folder }),
  })
  if (res.status === 412) {
    let detail = ''
    try {
      detail = (await res.json())?.detail ?? ''
    } catch {
      /* ignore */
    }
    const code =
      detail === 'google_account_mismatch'
        ? 'google_account_mismatch'
        : 'google_auth_required'
    const err = new Error(code) as Error & { code?: string }
    err.code = code
    throw err
  }
  if (!res.ok) throw new Error(`addDrive ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function googleAuthStatus(): Promise<{
  client_configured: boolean
  authenticated: boolean
  scopes: string[]
}> {
  const res = await fetch('/api/google_auth/status')
  if (!res.ok) throw new Error(`auth status ${res.status}: ${await res.text()}`)
  return res.json()
}

/** Open a popup to /api/google_auth/start and resolve when the popup
 *  signals success via window.postMessage from the callback page. */
export function googleAuthPopup(
  opts?: { prompt?: 'consent' | 'select_account' | 'select_account consent' },
  timeoutMs = 5 * 60 * 1000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = opts?.prompt
      ? `/api/google_auth/start?prompt=${encodeURIComponent(opts.prompt)}`
      : '/api/google_auth/start'
    const popup = window.open(url, 'inq-google-auth', 'popup,width=520,height=640')
    if (!popup) {
      reject(new Error('popup blocked — allow popups for inq and try again'))
      return
    }
    const onMessage = (e: MessageEvent) => {
      const d = e.data
      if (!d || typeof d !== 'object' || d.type !== 'inq:google_auth') return
      cleanup()
      if (d.ok) resolve()
      else reject(new Error('auth failed'))
    }
    const onTimer = window.setInterval(() => {
      if (popup.closed) {
        cleanup()
        reject(new Error('popup closed before auth completed'))
      }
    }, 500)
    const onTimeout = window.setTimeout(() => {
      cleanup()
      try {
        popup.close()
      } catch {
        /* noop */
      }
      reject(new Error('auth timed out'))
    }, timeoutMs)
    function cleanup() {
      window.removeEventListener('message', onMessage)
      window.clearInterval(onTimer)
      window.clearTimeout(onTimeout)
    }
    window.addEventListener('message', onMessage)
  })
}

import type { Thread } from './lib/threads'

export type StoredThread = Thread & { createdAt: string; updatedAt: string }

export async function fetchThreads(
  source?: string,
): Promise<{ source: string; threads: StoredThread[] }> {
  const qs = source ? `?source=${encodeURIComponent(source)}` : ''
  const res = await fetch(`/api/threads${qs}`)
  if (!res.ok) throw new Error(`threads ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function saveThread(thread: Thread, source?: string): Promise<StoredThread> {
  const now = new Date().toISOString().replace(/\.\d+Z$/, 'Z')
  const payload: StoredThread = {
    ...thread,
    createdAt: (thread as Partial<StoredThread>).createdAt ?? now,
    updatedAt: now,
  }
  const qs = source ? `?source=${encodeURIComponent(source)}` : ''
  const res = await fetch(`/api/threads${qs}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`saveThread ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteThread(id: string, source?: string): Promise<void> {
  const qs = source ? `?source=${encodeURIComponent(source)}` : ''
  const res = await fetch(
    `/api/threads/${encodeURIComponent(id)}${qs}`,
    { method: 'DELETE' },
  )
  if (!res.ok && res.status !== 404) {
    throw new Error(`deleteThread ${res.status}: ${await res.text()}`)
  }
}

export async function fetchTree(
  path = '',
  depth = 1,
  source?: string,
): Promise<Tree> {
  const params = new URLSearchParams()
  if (path) params.set('path', path)
  params.set('depth', String(depth))
  if (source) params.set('source', source)
  const res = await fetch(`/api/tree?${params}`)
  if (!res.ok) throw new Error(`tree ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function fetchFile(path: string, source?: string): Promise<FileData> {
  const qs = new URLSearchParams({ path })
  if (source) qs.set('source', source)
  const res = await fetch(`/api/file?${qs}`)
  if (!res.ok) throw new Error(`file ${res.status}: ${await res.text()}`)
  return res.json()
}
