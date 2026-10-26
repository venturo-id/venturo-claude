// Fungsi murni HUD: tanpa `$`, supaya bisa diuji langsung.
import type { HudDimension, HudGate, HudStatus, HudViolation } from '../types'

const DIMENSION_LABELS: Record<string, string> = {
  bug: 'Bug',
  structural: 'Struktur',
  readability: 'Baca',
  doc_sync: 'Doc',
}

const DIMENSION_ORDER = ['bug', 'structural', 'readability', 'doc_sync']

const GATE_LABELS: Record<string, string> = {
  commit_format: 'format commit',
  trivial_pr: 'PR < 5 baris',
  agent_docs: 'CLAUDE.md/AGENTS.md',
  doc_sync: 'doc sync',
  changelog: 'CHANGELOG',
  rules_fresh: 'rules basi',
}

type RawDimension = { score?: number | null; skipped?: boolean; findings?: number }
type RawViolation = {
  file?: string
  line?: number | null
  symbol?: string
  category?: string
  detail?: string
  points_final?: number
  heuristic?: boolean
}
type RawGate = { id?: string; ok?: boolean; effect?: string; detail?: string }
type RawStatus = {
  schema_version?: number
  head?: string
  diff_hash?: string
  changed?: { lines?: number }
  predicted?: {
    final?: number | null
    status?: string
    blocked_by?: string[]
    source?: string
    dimensions?: Record<string, RawDimension>
  }
  violations?: RawViolation[]
  gates?: RawGate[]
  rules?: { age_days?: number; stale?: boolean }
}

export const SUPPORTED_SCHEMA = 1

export function emptyStatus(error: string): HudStatus {
  return {
    final: null,
    status: 'error',
    blockedBy: [],
    source: 'static',
    dimensions: [],
    violations: [],
    gates: [],
    rulesAgeDays: 0,
    isRulesStale: false,
    changedLines: 0,
    head: '',
    diffHash: '',
    error,
  }
}

export function violationKey(v: RawViolation): string {
  return [v.file ?? '', v.symbol ?? '', v.category ?? ''].join('|')
}

/** Ubah output `kinerja_status.py --json` (schema 1) menjadi state HUD. */
export function parseStatus(stdout: string): HudStatus {
  let raw: RawStatus
  try {
    raw = JSON.parse(stdout) as RawStatus
  } catch {
    return emptyStatus('output kinerja_status bukan JSON')
  }
  if (raw.schema_version !== SUPPORTED_SCHEMA) {
    return emptyStatus(`schema_version ${String(raw.schema_version)} tidak didukung HUD`)
  }
  const predicted = raw.predicted ?? {}
  const dims = predicted.dimensions ?? {}
  const dimensions: HudDimension[] = DIMENSION_ORDER.filter(key => key in dims).map(key => {
    const dim = dims[key] ?? {}
    return {
      key,
      label: DIMENSION_LABELS[key] ?? key,
      score: dim.score ?? null,
      isSkipped: dim.skipped === true,
      findings: dim.findings ?? 0,
    }
  })
  // Poin terbesar dulu; dengan poin sama, temuan pasti (ambang) di atas heuristik (magic value).
  const ordered = [...(raw.violations ?? [])].sort(
    (a, b) => (b.points_final ?? 0) - (a.points_final ?? 0) || Number(a.heuristic === true) - Number(b.heuristic === true),
  )
  const violations: HudViolation[] = ordered.map(v => ({
    key: violationKey(v),
    file: v.file ?? '',
    line: v.line ?? null,
    symbol: v.symbol ?? '',
    category: v.category ?? '',
    detail: v.detail ?? '',
    points: v.points_final ?? 0,
  }))
  const gates: HudGate[] = (raw.gates ?? []).map(g => ({
    id: g.id ?? '',
    isOk: g.ok !== false,
    effect: g.effect ?? '',
    detail: g.detail ?? '',
  }))
  return {
    final: predicted.final ?? null,
    status: predicted.status ?? 'unscored',
    blockedBy: predicted.blocked_by ?? [],
    source: predicted.source ?? 'static',
    dimensions,
    violations,
    gates,
    rulesAgeDays: raw.rules?.age_days ?? 0,
    isRulesStale: raw.rules?.stale === true,
    changedLines: raw.changed?.lines ?? 0,
    head: raw.head ?? '',
    diffHash: raw.diff_hash ?? '',
    error: null,
  }
}

/** Pelanggaran di `next` yang belum ada di `prev`. */
export function newViolations(prev: HudStatus | null, next: HudStatus): HudViolation[] {
  if (prev === null || prev.error !== null) {
    return []
  }
  const known = new Set(prev.violations.map(v => v.key))
  return next.violations.filter(v => !known.has(v.key))
}

export function failedGates(status: HudStatus): HudGate[] {
  return status.gates.filter(g => !g.isOk && g.id !== 'rules_fresh')
}

export function gateLabel(id: string): string {
  return GATE_LABELS[id] ?? id
}

export function location(v: HudViolation): string {
  return v.line === null ? v.file : `${v.file}:${v.line}`
}

function scoreText(status: HudStatus): string {
  if (status.status === 'trivial') {
    return 'tidak dinilai (PR < 5 baris)'
  }
  if (status.final === null) {
    return 'belum ada prediksi'
  }
  return `≈${status.final}`
}

export function dimensionText(dim: HudDimension): string {
  if (dim.isSkipped || dim.score === null) {
    return `${dim.label} –`
  }
  return dim.findings > 0 ? `${dim.label} ${dim.score} (${dim.findings})` : `${dim.label} ${dim.score}`
}

/** Satu baris ringkas untuk band dan perintah /kinerja. */
export function summaryLine(status: HudStatus): string {
  if (status.error !== null) {
    return `Kinerja: ${status.error}`
  }
  const parts = [`Kinerja ${scoreText(status)}`, ...status.dimensions.map(dimensionText)]
  if (status.status === 'blocked') {
    parts.push(`⛔ tidak dinilai: ${status.blockedBy.map(gateLabel).join(', ')}`)
  }
  if (status.isRulesStale) {
    parts.push(`⚠ rules ${Math.floor(status.rulesAgeDays)} hari`)
  }
  return parts.join(' · ')
}

export function statusLineText(status: HudStatus): string {
  if (status.error !== null) {
    return 'kinerja ?'
  }
  if (status.status === 'blocked') {
    return `kinerja ⛔ ${status.blockedBy.map(gateLabel).join(', ')}`
  }
  const stale = status.isRulesStale ? ` · ⚠ rules ${Math.floor(status.rulesAgeDays)}h` : ''
  return `kinerja ${scoreText(status)}${stale}`
}

export function violationLine(v: HudViolation): string {
  const points = v.points > 0 ? `−${v.points} ` : ''
  const symbol = v.symbol === '' ? '' : ` ${v.symbol}`
  return `${points}${v.category}${symbol} ${location(v)} — ${v.detail}`
}

/** Teks toast untuk pelanggaran yang baru muncul setelah edit. */
export function toastText(added: HudViolation[]): string | undefined {
  const first = added[0]
  if (first === undefined) {
    return undefined
  }
  const more = added.length > 1 ? ` (+${added.length - 1} lainnya)` : ''
  return `Kinerja: ${violationLine(first)}${more}`
}

/** Laporan multi-baris untuk perintah /kinerja. */
export function reportText(status: HudStatus, limit: number): string {
  const lines = [summaryLine(status)]
  for (const gate of failedGates(status)) {
    lines.push(`  gate ${gateLabel(gate.id)}: ${gate.detail}`)
  }
  for (const v of status.violations.slice(0, limit)) {
    lines.push(`  ${violationLine(v)}`)
  }
  if (status.violations.length > limit) {
    lines.push(`  … ${status.violations.length - limit} pelanggaran lain`)
  }
  if (status.source === 'static' && status.error === null) {
    lines.push('  Dimensi bug belum diprediksi: jalankan skill venturo-kinerja-precheck.')
  }
  return lines.join('\n')
}

const THRESHOLD_LINE = /^\s*-?\s*([a-z_]+):\s*maks\s+(\d+)/gim

/** Ambil ambang `nama: maks N` dari badan rule structural. */
export function parseThresholds(structuralMd: string): Array<[string, number]> {
  const found: Array<[string, number]> = []
  for (const match of structuralMd.matchAll(THRESHOLD_LINE)) {
    const name = match[1]
    const max = match[2]
    if (name !== undefined && max !== undefined) {
      found.push([name, Number(max)])
    }
  }
  return found
}

export function parsePerFinding(scoringMd: string): number | undefined {
  const match = /^per_finding:\s*(\d+)/m.exec(scoringMd)
  return match?.[1] === undefined ? undefined : Number(match[1])
}

/** Section system prompt: ringkasan ambang review Kinerja, angka dari rules. */
export function rulesSection(thresholds: Array<[string, number]>, perFinding: number | undefined): string {
  const limits = thresholds.map(([name, max]) => `${name} ≤ ${max}`).join(', ')
  const deduction = perFinding === undefined ? '' : ` (−${perFinding} per temuan di dimensinya)`
  return [
    '# Standar code review Kinerja (venturo-kinerja-hud)',
    'Kode di repo ini dinilai otomatis oleh code review Kinerja. Tulis kode yang lolos di run pertama:',
    `- Ambang struktur pada fungsi/file yang kamu ubah${deduction}: ${limits}.`,
    '- Fungsi dihitung dari `func` sampai `}` termasuk baris kosong dan komentar; nesting dihitung dari badan fungsi.',
    '- Perubahan endpoint, DTO, route, atau skema membawa dokumen kontrak dan entri CHANGELOG di PR yang sama (doc sync bernilai 0 atau 100).',
    '- Setiap commit: `type(scope): deskripsi [KODE-123]` dengan kode issue Space; tanpa itu PR tidak dinilai.',
    '- Bug ditimbang per severity; error yang tidak ditangani, nil tanpa cek, dan race juga dihitung di dimensi struktur.',
    '- Rule lengkap: skill venturo-kinerja-rules. Sebelum push/PR: skill venturo-kinerja-precheck.',
  ].join('\n')
}

/** Alasan menahan `git push` / `gh pr create`, atau undefined bila boleh lanjut. */
export function pushBlockReason(status: HudStatus): string | undefined {
  const commit = status.gates.find(g => g.id === 'commit_format' && !g.isOk)
  if (commit === undefined) {
    return undefined
  }
  return [
    `venturo-kinerja-hud: push ditahan — ${commit.detail}.`,
    'Kinerja menolak commit tanpa format `type(scope): deskripsi` dan kode issue Space `[KODE-123]`; PR ini tidak akan dinilai.',
    'Perbaiki pesan commit (mis. `git rebase -i` / `git commit --amend`) setelah menanyakan kode issue ke user.',
  ].join(' ')
}

/** Peringatan sekali sebelum push bila masih ada pelanggaran. */
export function pushWarning(status: HudStatus, limit: number): string | undefined {
  if (status.violations.length === 0 && failedGates(status).length === 0) {
    return undefined
  }
  const top = status.violations.slice(0, limit).map(v => `- ${violationLine(v)}`)
  const gates = failedGates(status).map(g => `- gate ${gateLabel(g.id)}: ${g.detail}`)
  return [
    `venturo-kinerja-hud: prediksi ${summaryLine(status)}.`,
    'Review Kinerja menilai run terakhir sebelum merge; masalah berikut masih ada:',
    ...gates,
    ...top,
    'Sampaikan ke user dan tanyakan apakah tetap push. Bila user setuju, jalankan ulang perintah yang sama; HUD tidak menahannya dua kali untuk keadaan diff yang sama.',
  ].join('\n')
}

export function isPushCommand(command: string): boolean {
  return /(^|[\s;&|(])git\s+push\b/.test(command) || /(^|[\s;&|(])gh\s+pr\s+create\b/.test(command)
}

export function isGitPush(command: string): boolean {
  return /(^|[\s;&|(])git\s+push\b/.test(command)
}

export function isCommitCommand(command: string): boolean {
  return /(^|[\s;&|(])git\s+commit\b/.test(command)
}

const WATCHED_FILE = /(\.go$|(^|\/)(CLAUDE|AGENTS|CLAUDE\.local)\.md$|(^|\/)CHANGELOG\.md$|(^|\/)docs\/|(^|\/)go\.(mod|sum)$)/

export function isWatchedFile(path: string): boolean {
  return WATCHED_FILE.test(path)
}

export type InstalledPlugins = {
  plugins?: Record<string, Array<{ installPath?: string }>>
}

/** installPath plugin venturo-kinerja dari ~/.claude/plugins/installed_plugins.json. */
export function installedKinerjaPath(json: string): string | undefined {
  let parsed: InstalledPlugins
  try {
    parsed = JSON.parse(json) as InstalledPlugins
  } catch {
    return undefined
  }
  for (const [id, installs] of Object.entries(parsed.plugins ?? {})) {
    if (id.split('@')[0] !== 'venturo-kinerja') {
      continue
    }
    const path = installs.find(one => typeof one.installPath === 'string')?.installPath
    if (path !== undefined) {
      return path
    }
  }
  return undefined
}
