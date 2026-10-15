export type SddTask = { id: string; kind: 'test' | 'impl' | 'chore'; done: boolean; reqs: string[] }

export type SddChange = {
  id: string
  title: string
  status: string
  size: string
  adrs: string[]
  tasks: SddTask[]
}

export type SddCheck = { isOk: boolean; summary: string; lines: string[]; at: number; withTests: boolean }

export type SddAgent = { id: string; type: string; description: string; status: string }

declare module 'claude-code' {
  interface PluginState {
    sdd: {
      changes: SddChange[]
      archived: number
      root: string
      checks: Record<string, SddCheck>
      agents: SddAgent[]
      isBandHidden: boolean
      lastDeny: string
    }
  }
}
