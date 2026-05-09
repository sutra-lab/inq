import type { Extension } from '@codemirror/state'
import { javascript } from '@codemirror/lang-javascript'
import { python } from '@codemirror/lang-python'
import { markdown } from '@codemirror/lang-markdown'
import { html } from '@codemirror/lang-html'
import { css } from '@codemirror/lang-css'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { rust } from '@codemirror/lang-rust'
import { go } from '@codemirror/lang-go'
import { cpp } from '@codemirror/lang-cpp'
import { java } from '@codemirror/lang-java'

export function languageExtension(language: string): Extension[] {
  switch (language) {
    case 'javascript':
      return [javascript({ jsx: true })]
    case 'typescript':
      return [javascript({ jsx: true, typescript: true })]
    case 'python':
      return [python()]
    case 'markdown':
      return [markdown()]
    case 'html':
      return [html()]
    case 'css':
    case 'scss':
    case 'sass':
      return [css()]
    case 'json':
      return [json()]
    case 'yaml':
      return [yaml()]
    case 'rust':
      return [rust()]
    case 'go':
      return [go()]
    case 'c':
    case 'cpp':
      return [cpp()]
    case 'java':
      return [java()]
    default:
      return []
  }
}
