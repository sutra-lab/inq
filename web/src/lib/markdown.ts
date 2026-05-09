import type { Thread } from './threads'

function anchorStr(t: Thread): string {
  const { startLine: s, endLine: e } = t.anchor
  if (t.kind === 'pdf') return `p${s}`
  if (s === e) return `L${s}`
  return `L${s}-${e}`
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d+Z$/, 'Z')
}

export function renderThread(t: Thread): string {
  const out: string[] = []
  const sigil = t.mode === 'comment' ? '#' : '@'
  const verb = t.mode === 'comment' ? 'note' : 'ask'
  out.push(`## ${sigil} ${verb} · ${t.file}:${anchorStr(t)}`)

  const meta: string[] = []
  if (t.mode === 'ai' && t.model) meta.push(`model: ${t.model}`)
  if (meta.length) out.push(meta.join(' · '))
  out.push('')

  if (t.mode === 'comment') {
    for (const m of t.messages) {
      if (m.role !== 'user') continue
      const lines = (m.content || '').split('\n')
      for (const raw of lines) {
        const line = raw.trimEnd()
        if (!line) out.push('')
        else if (/^([-*])\s/.test(line)) out.push(line)
        else out.push(`- ${line}`)
      }
      out.push('')
    }
  } else {
    for (const m of t.messages) {
      const content = (m.content || '').trimEnd()
      if (!content) continue
      if (m.role === 'user') out.push(`**Q:** ${content}`)
      else out.push(content)
      out.push('')
    }
  }

  if (t.error) {
    out.push(`_error: ${t.error}_`)
    out.push('')
  }

  return out.join('\n').replace(/\n+$/, '\n')
}

export function renderAll(
  threads: Thread[],
  source: string,
  filterFile?: string,
): string {
  const rows = filterFile ? threads.filter((t) => t.file === filterFile) : threads
  const out: string[] = []
  out.push('# inq notes')
  out.push(`source: ${source}`)
  out.push(`exported: ${nowIso()}`)
  if (filterFile) out.push(`file: ${filterFile}`)
  out.push('')
  if (rows.length === 0) {
    out.push('_(no threads)_')
    out.push('')
    return out.join('\n')
  }
  for (const t of rows) {
    out.push(renderThread(t))
    out.push('---')
    out.push('')
  }
  return out.join('\n').replace(/\n+$/, '\n')
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through */
  }
  // Fallback: use a hidden textarea for older browsers / non-secure contexts.
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}
