export type HudDimension = {
  key: string
  label: string
  score: number | null
  isSkipped: boolean
  findings: number
}

export type HudViolation = {
  key: string
  file: string
  line: number | null
  symbol: string
  category: string
  detail: string
  points: number
}

export type HudGate = {
  id: string
  isOk: boolean
  effect: string
  detail: string
}

export type HudStatus = {
  final: number | null
  status: string
  blockedBy: string[]
  source: string
  dimensions: HudDimension[]
  violations: HudViolation[]
  gates: HudGate[]
  rulesAgeDays: number
  isRulesStale: boolean
  changedLines: number
  head: string
  diffHash: string
  // null bila kinerja_status versi lama belum melaporkan stack.
  stacks: string[] | null
  error: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'venturo-kinerja-hud': {
      status: HudStatus | null
      isHidden: boolean
      isCompact: boolean
      isExpanded: boolean
    }
  }
}
