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
      kind: 'text'
      language: string
      content: string
      size: number
    }
  | {
      path: string
      kind: 'pdf'
      size: number
      page_count: number
    }
  | {
      path: string
      kind: 'binary' | 'skipped'
      size: number
      skipped?: string
    }

export function rawUrl(path: string): string {
  return `/api/raw?path=${encodeURIComponent(path)}`
}

import type { Thread } from './lib/threads'

export type StoredThread = Thread & { createdAt: string; updatedAt: string }

export async function fetchThreads(): Promise<{ source: string; threads: StoredThread[] }> {
  const res = await fetch('/api/threads')
  if (!res.ok) throw new Error(`threads ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function saveThread(thread: Thread): Promise<StoredThread> {
  const now = new Date().toISOString().replace(/\.\d+Z$/, 'Z')
  const payload: StoredThread = {
    ...thread,
    createdAt: (thread as Partial<StoredThread>).createdAt ?? now,
    updatedAt: now,
  }
  const res = await fetch('/api/threads', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`saveThread ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteThread(id: string): Promise<void> {
  const res = await fetch(`/api/threads/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 404) {
    throw new Error(`deleteThread ${res.status}: ${await res.text()}`)
  }
}

export async function fetchTree(path = '', depth = 1): Promise<Tree> {
  const params = new URLSearchParams()
  if (path) params.set('path', path)
  params.set('depth', String(depth))
  const res = await fetch(`/api/tree?${params}`)
  if (!res.ok) throw new Error(`tree ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function fetchFile(path: string): Promise<FileData> {
  const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`)
  if (!res.ok) throw new Error(`file ${res.status}: ${await res.text()}`)
  return res.json()
}
