import { expect, test } from 'claude-code/testing'

const TEAMMATE_ARGS = 'claude --agent-id scout@team --agent-name scout --team-name team --parent-session-id abc'
// A lead whose prompt names both flags, unquoted as `ps` prints it.
const LEAD_ARGS = 'claude explain how --agent-id and --team-name work'

const BAND = {
  plugin: 'branch-usage',
  component: 'AbovePrompt',
  surface: 'terminal',
  props: {
    hasSurvey: false,
    isCollapsed: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

// A view with a branch, so the band has something to draw unless it is gated.
const VIEW = {
  branch: 'feat',
  sessionId: 'session-1',
  sessions: [],
  byModel: [],
  byAgent: [],
  totalUsd: 1.5,
}

type Calls = { opened: string[]; timers: number; gh: string[][] }
const calls = (): Calls => ({ opened: [], timers: 0, gh: [] })

// Each hook stands for the engine: a repository on branch `feat` with no remote
// and no usage files yet; `gh` fails. The store ignores the plugin's writes to
// the view, so the band keeps drawing the seeded one.
async function start($: any, on: any, args: string, c: Calls) {
  const store = new Map<string, { value: unknown; version: number }>([['view', { value: VIEW, version: 1 }]])
  on('state.get', (_: unknown, e: { key: string }) => ({ value: store.get(e.key) ?? { value: undefined, version: 0 } }))
  on('state.set', (_: unknown, e: { key: string; value: unknown }) => {
    const version = (store.get(e.key)?.version ?? 0) + 1
    if (e.key !== 'view') store.set(e.key, { value: e.value, version })
    return { value: { isSet: true, version } }
  })
  on('command.register', () => ({ value: { command: 'branch-usage' } }))
  on('tool.register', () => ({ value: {} }))
  on('process.hookEnv', () => ({ value: { CLAUDE_PID: '42' } }))
  on('process.run', (_: unknown, e: { argv?: string[]; command?: string[] }) => {
    const argv = e.argv ?? e.command ?? []
    const ok = (stdout: string) => ({ value: { exitCode: 0, stdout, stderr: '' } })
    if (argv[0] === 'ps') return ok(`${args}\n`)
    if (argv[0] === 'gh') c.gh.push(argv)
    if (argv.join(' ') === 'git rev-parse --abbrev-ref HEAD') return ok('feat\n')
    if (argv.join(' ') === 'git remote') return ok('')
    return { value: { exitCode: 1, stdout: '', stderr: 'not here' } }
  })
  on('session.repo', () => ({ value: { root: '/r' } }))
  on('session.root', () => ({ value: '/r' }))
  on('fs.exists', () => ({ value: false }))
  on('fs.list', () => ({ value: [] }))
  on('fs.write', () => ({ value: undefined }))
  on('ui.panes', () => ({ value: c.opened.map(id => ({ id, title: id, isShown: true, isFocused: false, isPlaced: true })) }))
  on('session.id', () => ({ value: 'session-1' }))
  on('session.info', () => ({ value: { transcriptPath: '/t.jsonl', platform: 'linux' } }))
  on('clock.every', () => {
    c.timers += 1
    return { value: {} }
  })
  on('ui.open', (_: unknown, e: { id: string }) => {
    if (!c.opened.includes(e.id)) c.opened.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.log', () => ({ value: undefined }))
  // What the engine draws when the plugin passes the band on.
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
}

const prLookups = (c: Calls) => c.gh.filter(argv => argv[1] === 'pr' && argv[2] === 'view').length

test('a terminal-pane teammate opens no pane, draws no band and looks up no PR', async ($, on) => {
  const c = calls()
  await start($, on, TEAMMATE_ARGS, c)
  expect(c.opened).toEqual([])
  expect(c.timers).toBe(0)
  expect(c.gh).toEqual([])

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})

test('/branch-usage in a teammate opens the pane, starts the timer and looks up the PR', async ($, on) => {
  const c = calls()
  on('command.run', () => ({ text: '' }))
  await start($, on, TEAMMATE_ARGS, c)

  await $.command.run({
    command: 'branch-usage',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: true, columns: 120 },
  })
  expect(c.opened).toEqual(['branch-usage'])
  expect(c.timers).toBe(1)
  expect(prLookups(c)).toBeGreaterThan(0)
})

test('a lead whose prompt names the teammate flags opens the pane and draws the band', async ($, on) => {
  const c = calls()
  await start($, on, LEAD_ARGS, c)
  expect(c.opened).toEqual(['branch-usage'])
  expect(c.timers).toBe(1)
  expect(prLookups(c)).toBeGreaterThan(0)

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text' }))?.text).toContain('feat')
  await ui.unmount()
})
