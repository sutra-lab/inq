import { EditorView } from '@codemirror/view'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { tags as t } from '@lezer/highlight'

type Palette = {
  bg: string
  bgElevated: string
  fg: string
  fgDim: string
  fgMute: string
  border: string
  accent: string
  selectionBg: string
  matchBg: string
  comment: string
  string: string
  keyword: string
  fn: string
  type: string
  num: string
  regex: string
  attr: string
  tag: string
  danger: string
}

const dark: Palette = {
  bg: '#0c0d0e',
  bgElevated: '#14171a',
  fg: '#e3e6e4',
  fgDim: '#8a8f93',
  fgMute: '#4a4f54',
  border: '#1f2326',
  accent: '#ffa657',
  selectionBg: 'rgba(255, 166, 87, 0.22)',
  matchBg: 'rgba(255, 166, 87, 0.12)',
  comment: '#5a6068',
  string: '#cda76b',
  keyword: '#ff7066',
  fn: '#7cc4d6',
  type: '#e8c172',
  num: '#c39ad6',
  regex: '#9bc28b',
  attr: '#6da7d6',
  tag: '#ff7066',
  danger: '#ff7066',
}

const light: Palette = {
  bg: '#f5f1e8',
  bgElevated: '#ebe6d8',
  fg: '#1a1714',
  fgDim: '#5a544a',
  fgMute: '#968d7e',
  border: '#d6cfba',
  accent: '#c25d1a',
  selectionBg: 'rgba(194, 93, 26, 0.18)',
  matchBg: 'rgba(194, 93, 26, 0.10)',
  comment: '#8a7e6c',
  string: '#a05d20',
  keyword: '#a83a2c',
  fn: '#2a5a85',
  type: '#8a6620',
  num: '#6e3a85',
  regex: '#4a6e30',
  attr: '#3a6a85',
  tag: '#a83a2c',
  danger: '#b03a2c',
}

function makeTheme(p: Palette, dark: boolean) {
  return EditorView.theme(
    {
      '&': {
        color: p.fg,
        backgroundColor: p.bg,
        height: '100%',
        fontFamily: "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace",
        fontSize: '12.5px',
      },
      '.cm-content': {
        caretColor: p.accent,
        padding: '8px 0',
      },
      '.cm-scroller': {
        fontFamily: 'inherit',
        lineHeight: '1.6',
      },
      '&.cm-focused': {
        outline: 'none',
      },
      '.cm-gutters': {
        backgroundColor: p.bg,
        color: p.fgMute,
        border: 'none',
        borderRight: `1px solid ${p.border}`,
        paddingRight: '4px',
      },
      '.cm-activeLineGutter': {
        backgroundColor: 'transparent',
        color: p.fgDim,
      },
      '.cm-activeLine': {
        backgroundColor: 'transparent',
      },
      '.cm-lineNumbers .cm-gutterElement': {
        padding: '0 6px 0 12px',
        minWidth: '28px',
      },
      '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection':
        {
          backgroundColor: p.selectionBg,
        },
      '.cm-cursor, .cm-dropCursor': {
        borderLeftColor: p.accent,
      },
      '.cm-selectionMatch': {
        backgroundColor: p.matchBg,
      },
      '.cm-matchingBracket, .cm-nonmatchingBracket': {
        backgroundColor: p.bgElevated,
        outline: `1px solid ${p.border}`,
      },
      '.cm-searchMatch': {
        backgroundColor: p.matchBg,
      },
      '.cm-tooltip': {
        border: `1px solid ${p.border}`,
        backgroundColor: p.bgElevated,
        color: p.fg,
      },
      '.inq-anchor-line': {
        boxShadow: `inset 2px 0 0 ${p.accent}`,
        backgroundColor: dark
          ? 'rgba(255, 166, 87, 0.06)'
          : 'rgba(194, 93, 26, 0.06)',
      },
      '.inq-anchor-gutter': {
        color: p.accent,
      },
    },
    { dark },
  )
}

function makeHighlight(p: Palette) {
  return HighlightStyle.define([
    { tag: t.comment, color: p.comment, fontStyle: 'italic' },
    { tag: t.lineComment, color: p.comment, fontStyle: 'italic' },
    { tag: t.blockComment, color: p.comment, fontStyle: 'italic' },
    { tag: [t.string, t.special(t.string)], color: p.string },
    { tag: [t.number, t.bool, t.null], color: p.num },
    { tag: [t.keyword, t.modifier, t.controlKeyword, t.operatorKeyword], color: p.keyword },
    { tag: [t.definition(t.variableName), t.definition(t.propertyName)], color: p.fg },
    { tag: [t.function(t.variableName), t.function(t.propertyName)], color: p.fn },
    { tag: [t.className, t.typeName], color: p.type },
    { tag: [t.tagName], color: p.tag },
    { tag: [t.attributeName, t.propertyName], color: p.attr },
    { tag: [t.variableName], color: p.fg },
    { tag: [t.regexp, t.escape], color: p.regex },
    { tag: [t.heading], color: p.accent, fontWeight: 'bold' },
    { tag: [t.link, t.url], color: p.fn, textDecoration: 'underline' },
    { tag: [t.emphasis], fontStyle: 'italic' },
    { tag: [t.strong], fontWeight: 'bold' },
    { tag: [t.invalid], color: p.danger, textDecoration: 'underline' },
  ])
}

export const inqDarkBundle = [makeTheme(dark, true), syntaxHighlighting(makeHighlight(dark))]
export const inqLightBundle = [makeTheme(light, false), syntaxHighlighting(makeHighlight(light))]

export function bundleForTheme(theme: 'dark' | 'light') {
  return theme === 'light' ? inqLightBundle : inqDarkBundle
}
