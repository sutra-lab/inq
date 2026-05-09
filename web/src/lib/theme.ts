import { useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'inq.theme'

function readInitial(): Theme {
  if (typeof window === 'undefined') return 'dark'
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches
  return prefersLight ? 'light' : 'dark'
}

function applyTheme(t: Theme) {
  const root = document.documentElement
  root.classList.toggle('theme-light', t === 'light')
}

export function useTheme(): [Theme, (t: Theme) => void, () => void] {
  const [theme, setTheme] = useState<Theme>(readInitial)

  useEffect(() => {
    applyTheme(theme)
    try {
      window.localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* ignore storage errors (private mode, etc.) */
    }
  }, [theme])

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  return [theme, setTheme, toggle]
}
