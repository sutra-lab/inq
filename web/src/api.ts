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

export type FileData = {
  path: string
  language: string
  content: string
  size: number
  skipped?: 'too_large' | 'binary' | 'encoding'
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
