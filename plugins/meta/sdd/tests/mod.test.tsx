import { expect, test } from 'claude-code/testing'

const SURFACES = ['terminal', 'desktop'] as const
const SITE = { scroll: { offset: 0, bodyRows: 20 }, view: {} }

test('the lead editing a living spec is refused in the session', async ($, on) => {
  // the engine's answers beneath the plugin: a project at /repo with no sdd.json
  const root = '/repo'
  on('session.root', () => ({ value: root }))
  on('session.cwd', () => ({ value: root }))
  on('fs.read', () => {
    throw new Error('ENOENT')
  })
  let reachedTool = false
  on('tool.call', { tool: 'Edit' }, () => {
    reachedTool = true
    return { result: 'edited' }
  })
  const ran = await $.tool.call({
    tool: 'Edit',
    file_path: `${root}/specs/auth/spec.md`,
    old_string: 'a',
    new_string: 'b',
  })
  const refusal = 'deny' in ran && ran.deny !== undefined ? ran.deny : ran.text ?? ''
  expect(String(refusal)).toContain('sdd sync')
  expect(reachedTool).toBe(false)
})

test('the pane says how to start when no change is open', async $ => {
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'sdd',
      surface,
      component: 'Pane',
      requestId: 'sdd',
      props: { title: 'Spec-driven workflow', isFocused: false, bodyColumns: 80, placement: 'dock', ...SITE },
    })
    expect(await ui.find({ type: 'Text', text: /No open change/ })).toBeDefined()
    await ui.unmount()
  }
})

test('the band shows the most active change and its progress', async ($, on) => {
  const status = {
    root: '/repo',
    archived: 2,
    changes: [
      { id: 'old-draft', title: 'x', status: 'draft', size: 'change', adrs: [], tasks: [] },
      {
        id: 'add-login',
        title: 'Add login',
        status: 'implementing',
        size: 'change',
        adrs: ['ADR-0002'],
        tasks: [
          { id: 'T1', kind: 'test', done: true, reqs: ['REQ-AUTH-001'] },
          { id: 'T2', kind: 'impl', done: false, reqs: ['REQ-AUTH-001'] },
        ],
      },
    ],
  }
  on('session.root', () => ({ value: '/repo' }))
  on('process.run', (_$, e) => {
    expect(e.argv.slice(-2)).toEqual(['status', '--json'])
    return { value: { exitCode: 0, stdout: JSON.stringify(status), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('agent.list', () => ({ value: [] }))
  await $.command.run({ command: 'sdd', args: 'refresh', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 100 } })

  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'sdd',
      surface,
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 100, ...SITE },
    })
    expect(await ui.find({ type: 'Text', text: 'add-login' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Implement · implementing · 1\/2 tasks/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /\+1 open/ })).toBeDefined()
    expect(await ui.find({ key: 'open' })).toBeDefined()
    await ui.unmount()
  }
})

test('the phase pane marks the current phase of the most active change', async ($, on) => {
  const status = {
    root: '/repo',
    archived: 0,
    changes: [
      {
        id: 'add-login',
        title: 'Add login',
        status: 'implementing',
        size: 'change',
        adrs: [],
        tasks: [
          { id: 'T1', kind: 'test', done: true, reqs: ['REQ-AUTH-001'] },
          { id: 'T2', kind: 'impl', done: false, reqs: ['REQ-AUTH-001'] },
        ],
      },
    ],
  }
  on('session.root', () => ({ value: '/repo' }))
  on('process.run', () => ({
    value: { exitCode: 0, stdout: JSON.stringify(status), stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('agent.list', () => ({ value: [] }))
  await $.command.run({ command: 'sdd', args: 'refresh', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 100 } })

  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'sdd',
      surface,
      component: 'Pane',
      requestId: 'sdd-phase',
      props: { title: 'sdd phase', isFocused: false, bodyColumns: 80, placement: 'dock', ...SITE },
    })
    expect(await ui.find({ type: 'Text', text: /▶ 6\. Implement/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /✓ 5\. Acceptance tests/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /· 7\. Verify/ })).toBeDefined()
    await ui.unmount()
  }
})

test('the phase pane says triage when no change is open', async $ => {
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'sdd',
      surface,
      component: 'Pane',
      requestId: 'sdd-phase',
      props: { title: 'sdd phase', isFocused: false, bodyColumns: 80, placement: 'dock', ...SITE },
    })
    expect(await ui.find({ type: 'Text', text: /No open change: triage/ })).toBeDefined()
    await ui.unmount()
  }
})

test('the band stays out of the way when no change is open', async ($, on) => {
  // stands for the engine's own band beneath the plugin
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text key="engine">engine band</Text>
  })
  for (const surface of SURFACES) {
    const ui = await $.ui.mount({
      plugin: 'sdd',
      surface,
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 80, ...SITE },
    })
    expect(await ui.find({ key: 'open' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /engine band/ })).toBeDefined()
    await ui.unmount()
  }
})

test('the main conversation is the lead: its system prompt ends with the lead section', async ($, on) => {
  // stands for the engine's own composition beneath the plugin
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'engine intro', scope: 'shared' }] }))
  const { sections } = await $.prompt.compose({
    model: 'claude-test',
    promptModel: 'claude-test',
    surfaces: ['terminal'],
    tools: [],
    outputStyle: null,
    traits: [],
  })
  expect(sections.map(s => s.id)).toEqual(['intro', 'sdd:lead'])
  expect(sections[1].scope).toBe('session')
  expect(sections[1].text).toContain('`sdd:change`')
})
