import { useEffect, useState } from 'react'
import { fetchTree, type TreeNode } from '../api'

type Props = {
  source: string
  selectedPath: string | null
  onSelect: (path: string) => void
}

export function FileTree({ source, selectedPath, onSelect }: Props) {
  const [roots, setRoots] = useState<TreeNode[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setRoots(null)
    setError(null)
    fetchTree('', 1, source)
      .then((t) => setRoots(t.children))
      .catch((e) => setError(String(e)))
  }, [source])

  if (error) {
    return <div className="px-3 py-2 text-[11px] text-danger break-words">{error}</div>
  }
  if (!roots) {
    return <div className="px-3 py-2 text-[11px] text-fg-mute">loading…</div>
  }

  return (
    <ul className="py-1 select-none">
      {roots.map((n) => (
        <Node
          key={n.path}
          node={n}
          depth={0}
          source={source}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </ul>
  )
}

type NodeProps = {
  node: TreeNode
  depth: number
  source: string
  selectedPath: string | null
  onSelect: (path: string) => void
}

function Node({ node, depth, source, selectedPath, onSelect }: NodeProps) {
  const [open, setOpen] = useState(false)
  const [children, setChildren] = useState<TreeNode[] | null>(node.children ?? null)
  const [loading, setLoading] = useState(false)

  const isFile = node.type === 'file'
  const isSelected = selectedPath === node.path

  const handleClick = async () => {
    if (isFile) {
      onSelect(node.path)
      return
    }
    if (!open && children == null) {
      setLoading(true)
      try {
        const t = await fetchTree(node.path, 1, source)
        setChildren(t.children)
      } catch {
        setChildren([])
      } finally {
        setLoading(false)
      }
    }
    setOpen((v) => !v)
  }

  const indent = depth * 12 + 10

  return (
    <li>
      <button
        onClick={handleClick}
        className={`relative w-full text-left flex items-center gap-1.5 py-[2px] pr-2 text-[12.5px] hover:bg-bg-elevated ${
          isSelected
            ? 'bg-bg-active text-accent'
            : isFile
              ? 'text-fg-dim hover:text-fg'
              : 'text-fg hover:text-fg'
        }`}
        style={{ paddingLeft: `${indent}px` }}
      >
        {isSelected && (
          <span
            aria-hidden
            className="absolute left-0 top-0 bottom-0 w-[2px] bg-accent"
          />
        )}
        <span className="w-3 inline-block text-fg-mute text-[9px] shrink-0">
          {isFile ? '' : open ? '▾' : '▸'}
        </span>
        <span className="truncate">{node.name}</span>
      </button>
      {open && loading && (
        <div
          className="text-[10px] text-fg-mute py-0.5"
          style={{ paddingLeft: `${indent + 16}px` }}
        >
          loading…
        </div>
      )}
      {open && children && (
        <ul>
          {children.map((c) => (
            <Node
              key={c.path}
              node={c}
              depth={depth + 1}
              source={source}
              selectedPath={selectedPath}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
