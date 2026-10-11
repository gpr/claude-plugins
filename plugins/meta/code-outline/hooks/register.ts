import type { Register } from 'claude-code'
import { formatHit, parseOutline, sectionAt, type Section } from './kb'

const TOOL = 'mcp__code-outline__kb_grep'

type Input = { pattern: string; fixed?: boolean; scope?: 'all' | 'signature'; path?: string; max?: number }
type RgEvent = { type: string; data: { path?: { text: string }; line_number?: number } }

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.tool.register({
      name: 'kb_grep',
      isDeferred: false,
      description:
        'Search the code-outline cache (.kb/files/) for functions, classes and sections by name, signature, description or call graph. ' +
        'Each hit is `path:start-end  signature — description  [calls … | called by … | external …]`: read it with Read(file_path=path, offset=start, limit=end-start+1). ' +
        'Only files that were fully read once have an outline, so "no match" does not mean the code is absent: fall back to Grep. ' +
        'A hit marked (stale) comes from an older version of the file; check its range before trusting it.',
      inputSchema: {
        type: 'object',
        properties: {
          pattern: { type: 'string', description: 'Case-insensitive regex (ripgrep syntax).' },
          fixed: { type: 'boolean', description: 'Treat pattern as a literal string.' },
          scope: {
            type: 'string',
            enum: ['all', 'signature'],
            description: '"all" (default) matches signature, description and call graph; "signature" matches only the section header, for exact name lookups.',
          },
          path: { type: 'string', description: 'Glob on the source path, e.g. "src/**/*.py".' },
          max: { type: 'number', description: 'Maximum hits (default 50).' },
        },
        required: ['pattern'],
      },
    })
    return next(e)
  })

  on('tool.call', { tool: TOOL }, async ($, e) => {
    const input = e as unknown as Input & { tool: string }
    const root = await $.session.cwd()
    const kb = `${root}/.kb/files`
    if (!(await $.fs.exists(kb))) return { result: 'No outline exists yet: no source file has been fully read in this project.' }

    const glob = input.path ? `${input.path.replace(/^\.?\//, '')}.md` : '**/*.md'
    const rg = await $.process.run(
      ['rg', '--json', '-i', '--no-messages', ...(input.fixed ? ['-F'] : []), '-g', glob, '-e', input.pattern, '--', '.'],
      { cwd: kb, timeoutMs: 10_000 },
    ).catch(() => undefined)
    if (!rg) return { deny: 'kb_grep needs ripgrep (rg) on PATH.' }
    if (rg.exitCode === 1) return { result: 'no match' }
    if (rg.exitCode !== 0) return { deny: `rg failed: ${rg.stderr.trim().split('\n')[0] || `exit ${rg.exitCode}`}` }

    const byFile = new Map<string, number[]>()
    for (const raw of rg.stdout.split('\n')) {
      if (!raw) continue
      const ev = JSON.parse(raw) as RgEvent
      const file = ev.data.path?.text
      if (ev.type !== 'match' || !file || ev.data.line_number === undefined) continue
      byFile.set(file, [...(byFile.get(file) ?? []), ev.data.line_number])
    }

    const max = Math.max(1, Math.floor(input.max ?? 50))
    const hits: string[] = []
    let total = 0
    let pending = 0
    for (const [file, matched] of [...byFile].sort(([a], [b]) => (a < b ? -1 : 1))) {
      const outline = parseOutline(await $.fs.read(`${kb}/${file}`), file.replace(/\.md$/, ''))
      const seen = new Set<Section>()
      for (const n of matched) {
        const s = sectionAt(outline, n)
        if (!s || seen.has(s)) continue
        if (input.scope === 'signature' && n !== s.line) continue
        seen.add(s)
      }
      if (seen.size === 0) continue
      const sum = await $.process.run(['sha256sum', outline.source], { cwd: root }).catch(() => undefined)
      const isStale = (sum?.stdout.split(' ')[0] ?? '') !== outline.sha
      for (const s of [...seen].sort((a, b) => a.start - b.start)) {
        total++
        if (hits.length >= max) continue
        if (!s.desc) pending++
        hits.push(formatHit(outline.source, s, isStale))
      }
    }
    if (hits.length === 0) return { result: 'no match' }
    const notes = [
      total > hits.length ? `... ${total - hits.length} more hits, refine the pattern or raise max` : '',
      pending ? `note: ${pending} hit(s) have no description yet (enrichment pending)` : '',
    ].filter(Boolean)
    return { result: [...hits, ...notes].join('\n') }
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'kb_grep failed.' }))
}
