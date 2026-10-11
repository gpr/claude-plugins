// Pure helpers for the kb_grep tool: parse an outline file, map ripgrep line hits to sections.

export type Section = { start: number; end: number; sig: string; desc: string; graph: string; line: number; last: number }
export type Outline = { source: string; sha: string; sections: Section[] }

const HEADER = /^#+ L(\d+)-(\d+) (.*)$/

export function parseOutline(text: string, fallbackSource: string): Outline {
  const lines = text.split('\n')
  const meta: Record<string, string> = {}
  let i = 0
  if (lines[0] === '---') {
    for (i = 1; i < lines.length && lines[i] !== '---'; i++) {
      const at = lines[i].indexOf(': ')
      if (at > 0) meta[lines[i].slice(0, at)] = lines[i].slice(at + 2)
    }
    i++
  }
  const sections: Section[] = []
  let cur: Section | undefined
  for (; i < lines.length; i++) {
    const line = lines[i]
    const m = HEADER.exec(line)
    if (m) {
      cur = { start: +m[1], end: +m[2], sig: m[3], desc: '', graph: '', line: i + 1, last: i + 1 }
      sections.push(cur)
    } else if (cur) {
      cur.last = i + 1
      if (line.startsWith('- desc: ')) {
        const d = line.slice(8).trim()
        cur.desc = d === '_(pending)_' ? '' : d
      } else if (line.startsWith('- ')) cur.graph = line.slice(2).trim()
    }
  }
  return { source: meta.source ?? fallbackSource, sha: meta.source_sha256 ?? '', sections }
}

/** The section a 1-based outline line belongs to, header lines included; frontmatter lines belong to none. */
export function sectionAt(outline: Outline, line: number): Section | undefined {
  return outline.sections.find(s => line >= s.line && line <= s.last)
}

export function formatHit(source: string, s: Section, isStale: boolean): string {
  let out = `${source}:${s.start}-${s.end}  ${s.sig}`
  if (s.desc) out += `  — ${s.desc}`
  if (s.graph) out += `  [${s.graph}]`
  if (isStale) out += '  (stale: source changed since outline)'
  return out
}
