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
