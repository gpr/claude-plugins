export type SddTask = { id: string; kind: 'test' | 'impl' | 'chore'; done: boolean; refs: string[] }

export type SddChange = {
  id: string
  title: string
  status: string
  size: string
  adrs: string[]
  tasks: SddTask[]
  /** From state.json: the stored workflow phase, the PR number and the change branch. */
  phase?: string | null
  pr?: number | null
  branch?: string | null
  /** From state.json: changes that must be merged into the base before this one continues. */
  requires?: string[]
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
      /** The git branch checked out in the session's cwd ('' outside git). */
      branch: string
      /** The status groups of the /sdd pane the person unfolded. */
      expanded: string[]
    }
  }
}
