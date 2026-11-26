import { expect, test } from 'claude-code/testing'

const TEAMMATE_ARGS = 'claude --agent-id scout@team --agent-name scout --team-name team --parent-session-id abc'
const LEAD_ARGS = 'claude "what does --agent-id do"'

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

// Each hook stands for the engine. The git and gh calls fail, so refresh keeps
// the seeded view: the store below ignores the plugin's writes to it.
async function start($: any, on: any, args: string, opened: string[], timers: number[] = []) {
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
    return argv[0] === 'ps'
      ? { value: { exitCode: 0, stdout: `${args}\n`, stderr: '' } }
      : { value: { exitCode: 1, stdout: '', stderr: 'no git here' } }
  })
  on('session.repo', () => ({ value: null }))
  on('session.id', () => ({ value: 'session-1' }))
  on('session.info', () => ({ value: { transcriptPath: '/t.jsonl', platform: 'linux' } }))
  on('clock.every', () => {
    timers.push(1)
    return { value: {} }
  })
  on('ui.open', (_: unknown, e: { id: string }) => {
    opened.push(e.id)
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

test('a terminal-pane teammate opens no pane and draws no band', async ($, on) => {
  const opened: string[] = []
  await start($, on, TEAMMATE_ARGS, opened)
  expect(opened).toEqual([])

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})

test('a teammate starts the refresh timer when /branch-usage opens its pane', async ($, on) => {
  const opened: string[] = []
  const timers: number[] = []
  on('command.run', () => ({ text: '' }))
  await start($, on, TEAMMATE_ARGS, opened, timers)
  expect(timers.length).toBe(0)

  await $.command.run({
    command: 'branch-usage',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: true, columns: 120 },
  })
  expect(opened).toEqual(['branch-usage'])
  expect(timers.length).toBe(1)
})

test('the lead opens the pane and draws the band', async ($, on) => {
  const opened: string[] = []
  const timers: number[] = []
  await start($, on, LEAD_ARGS, opened, timers)
  expect(opened).toEqual(['branch-usage'])
  expect(timers.length).toBe(1)

  const ui = await $.ui.mount(BAND)
  expect((await ui.find({ type: 'Text' }))?.text).toContain('feat')
  await ui.unmount()
})
