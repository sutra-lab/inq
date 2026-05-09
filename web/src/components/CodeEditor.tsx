import { useEffect, useRef } from 'react'
import { basicSetup, EditorView } from 'codemirror'
import {
  Compartment,
  EditorState,
  RangeSetBuilder,
  StateEffect,
  StateField,
  Prec,
} from '@codemirror/state'
import { Decoration, type DecorationSet, keymap } from '@codemirror/view'
import { languageExtension } from '../lib/cmLang'
import { bundleForTheme } from '../lib/cmTheme'
import type { Theme } from '../lib/theme'

export type Anchor = { startLine: number; endLine: number }

type Props = {
  value: string
  language: string
  anchors: Anchor[]
  theme: Theme
  onAsk: (anchor: Anchor) => void
}

const setAnchorsEffect = StateEffect.define<Anchor[]>()

const anchorField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none
  },
  update(deco, tr) {
    let next = deco.map(tr.changes)
    for (const e of tr.effects) {
      if (e.is(setAnchorsEffect)) {
        const builder = new RangeSetBuilder<Decoration>()
        const total = tr.state.doc.lines
        const seen = new Set<number>()
        const sorted = [...e.value].sort((a, b) => a.startLine - b.startLine)
        for (const a of sorted) {
          const start = Math.max(1, a.startLine)
          const end = Math.min(total, a.endLine)
          for (let line = start; line <= end; line++) {
            if (seen.has(line)) continue
            seen.add(line)
            const info = tr.state.doc.line(line)
            builder.add(
              info.from,
              info.from,
              Decoration.line({ attributes: { class: 'inq-anchor-line' } }),
            )
          }
        }
        next = builder.finish()
      }
    }
    return next
  },
  provide: (f) => EditorView.decorations.from(f),
})

export function CodeEditor({ value, language, anchors, theme, onAsk }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const langCompartment = useRef(new Compartment()).current
  const themeCompartment = useRef(new Compartment()).current
  const onAskRef = useRef(onAsk)

  useEffect(() => {
    onAskRef.current = onAsk
  }, [onAsk])

  // Mount once
  useEffect(() => {
    if (!hostRef.current) return

    const askKeymap = Prec.highest(
      keymap.of([
        {
          key: '@',
          preventDefault: true,
          run: (view) => {
            const sel = view.state.selection.main
            const startLine = view.state.doc.lineAt(sel.from).number
            const endLine = view.state.doc.lineAt(sel.to).number
            onAskRef.current({ startLine, endLine })
            return true
          },
        },
      ]),
    )

    const state = EditorState.create({
      doc: value,
      extensions: [
        askKeymap,
        basicSetup,
        EditorState.readOnly.of(true),
        EditorState.tabSize.of(2),
        langCompartment.of(languageExtension(language)),
        anchorField,
        themeCompartment.of(bundleForTheme(theme)),
      ],
    })

    const view = new EditorView({ state, parent: hostRef.current })
    viewRef.current = view

    // initial anchors push
    view.dispatch({ effects: setAnchorsEffect.of(anchors) })

    return () => {
      view.destroy()
      viewRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Update content + language when file changes
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current !== value) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: value },
        effects: [
          langCompartment.reconfigure(languageExtension(language)),
          setAnchorsEffect.of(anchors),
        ],
      })
    } else {
      view.dispatch({
        effects: [
          langCompartment.reconfigure(languageExtension(language)),
          setAnchorsEffect.of(anchors),
        ],
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, language])

  // Update anchors when threads change
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    view.dispatch({ effects: setAnchorsEffect.of(anchors) })
  }, [anchors])

  // Update theme when toggled
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    view.dispatch({ effects: themeCompartment.reconfigure(bundleForTheme(theme)) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme])

  return <div ref={hostRef} className="h-full overflow-auto" />
}
