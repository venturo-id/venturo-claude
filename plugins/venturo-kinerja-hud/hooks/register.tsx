import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { HudStatus } from '../types'
import {
  emptyStatus,
  failedGates,
  installedKinerjaPath,
  isCommitCommand,
  isGitPush,
  isPushCommand,
  detectStacks,
  dimensionText,
  isWatchedFile,
  MODE_HINT,
  modeLine,
  newViolations,
  parsePerFinding,
  parseStatus,
  parseThresholds,
  pushBlockReason,
  pushWarning,
  reportText,
  rulesSection,
  statusLineText,
  summaryLine,
  toastText,
  violationLine,
} from './lib'

const PLUGIN = 'venturo-kinerja-hud'
const status = atom({ plugin: 'venturo-kinerja-hud', key: 'status' } as const, null)
const isHidden = atom({ plugin: 'venturo-kinerja-hud', key: 'isHidden' } as const, false)
const isCompact = atom({ plugin: 'venturo-kinerja-hud', key: 'isCompact' } as const, false)
const isExpanded = atom({ plugin: 'venturo-kinerja-hud', key: 'isExpanded' } as const, false)

const STATUS_TIMEOUT_MS = 20_000
const GIT_TIMEOUT_MS = 5_000
// Edit di luar Claude (IDE, git checkout) tertangkap lewat polling git diff murah;
// kinerja_status hanya dijalankan ulang bila sidik diff berubah.
const POLL_MS = 8_000
const MAX_UNTRACKED_STAT = 50
const GH_TIMEOUT_MS = 8_000
// Edit beruntun dalam satu turn cukup dihitung ulang sekali per jeda ini;
// sisanya ditangkap turn.complete.
const MIN_REFRESH_GAP_MS = 4_000
const REPORT_LIMIT = 8
const BAND_LIMIT = 5
const PUSH_WARNING_LIMIT = 5
const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit'])
const PANE_ID = 'kinerja'
const PANE_TITLE = 'Kinerja'
const PANE_LIMIT = 12
const STATE_DIR = '.claude/venturo-kinerja'

// State sesi modul; register dijalankan ulang (dan state ini mulai dari awal) setiap reload.
const hud = {
  cwd: '',
  kinerjaRoot: undefined as string | undefined,
  isActive: false,
  rules: undefined as { thresholds: Array<[string, number]>; perFinding: number | undefined } | undefined,
  // Panel dibuka setelah status pertama folder ini diketahui (mode off tidak membuka panel).
  isPaneWanted: false,
  lastRefreshAt: 0,
  isDirty: false,
  running: undefined as Promise<HudStatus> | undefined,
  // Kunci keadaan diff yang sudah diperingatkan saat push (peringatan sekali).
  warnedPushKey: undefined as string | undefined,
  // Sidik diff terakhir yang sudah dihitung statusnya.
  fingerprint: '',
  isPolling: false,
  // Stack dari manifest root sampai kinerja_status pertama selesai; sesudahnya
  // `stacks` laporan status (termasuk subfolder monorepo) yang jadi acuan.
  hasStack: false,
  // Diagnostik: apa yang diminta surface dari mod ini (ditulis ke hud-debug.json).
  debug: {
    surfaces: [] as string[],
    renders: {} as Record<string, number>,
    pane: 'belum dibuka',
    startedAt: '',
  },
}

// Surface selain terminal (desktop app, VS Code, mobile) menggambar lewat jalur
// jarak jauh; tidak semua host menggambar band AbovePrompt, sedangkan Pane
// digambar di setiap surface. Pane dibuka otomatis hanya untuk surface itu.
function isRemoteSurface(surface: string): boolean {
  return surface !== 'terminal'
}

async function writeDebug($: EngineInterface): Promise<void> {
  if (hud.cwd === '') {
    return
  }
  const dir = `${hud.cwd}/${STATE_DIR}`
  if (!(await $.fs.exists(`${dir}/.gitignore`))) {
    await $.fs.write(`${dir}/.gitignore`, '*\n')
  }
  const snapshot = {
    startedAt: hud.debug.startedAt,
    cwd: hud.cwd,
    kinerjaRoot: hud.kinerjaRoot ?? null,
    isActive: hud.isActive,
    hasStack: hud.hasStack,
    surfaces: hud.debug.surfaces,
    renders: hud.debug.renders,
    pane: hud.debug.pane,
  }
  await $.fs.write(`${dir}/hud-debug.json`, `${JSON.stringify(snapshot, null, 2)}\n`)
}

function writeDebugInBackground($: EngineInterface): void {
  writeDebug($).catch(() => undefined)
}

/** Catat permintaan render pertama per komponen+surface (dan hitung sisanya). */
function noteRender($: EngineInterface, component: string, surface: string): void {
  const key = `${component}@${surface}`
  const seen = hud.debug.renders[key] ?? 0
  hud.debug.renders[key] = seen + 1
  if (seen === 0) {
    writeDebugInBackground($)
  }
}

async function openPane($: EngineInterface): Promise<string> {
  const opened = await $.ui.open({ id: PANE_ID, title: PANE_TITLE })
  hud.debug.pane = opened.isPlaced ? 'terbuka' : `belum tergambar: ${opened.reason}`
  writeDebugInBackground($)
  return hud.debug.pane
}

async function openPaneForRemoteSurfaces($: EngineInterface): Promise<void> {
  const surfaces = await $.session.surfaces()
  hud.debug.surfaces = [...surfaces]
  if (surfaces.some(isRemoteSurface)) {
    await openPane($)
  } else {
    writeDebugInBackground($)
  }
}

function debugText(): string {
  return [
    'HUD Kinerja — diagnostik',
    `  cwd: ${hud.cwd}`,
    `  plugin venturo-kinerja: ${hud.kinerjaRoot ?? 'tidak ditemukan'}`,
    `  aktif: ${hud.isActive} · stack dikenali: ${hud.hasStack}`,
    `  surface terpasang: ${hud.debug.surfaces.join(', ') || '(belum ada)'}`,
    `  render diminta: ${Object.entries(hud.debug.renders).map(([k, n]) => `${k}×${n}`).join(', ') || '(belum ada)'}`,
    `  panel: ${hud.debug.pane}`,
    `  file: ${hud.cwd}/${STATE_DIR}/hud-debug.json`,
  ].join('\n')
}

async function findKinerjaRoot($: EngineInterface): Promise<string | undefined> {
  const candidates: string[] = []
  const fromEnv = await $.env.get('VENTURO_KINERJA_ROOT')
  if (fromEnv !== undefined && fromEnv !== '') {
    candidates.push(fromEnv)
  }
  // Checkout repo venturo-claude atau --plugin-dir: plugin bersebelahan.
  candidates.push(`${$.plugin.root}/../venturo-kinerja`)
  const home = await $.env.get('HOME')
  if (home !== undefined) {
    const installed = `${home}/.claude/plugins/installed_plugins.json`
    if (await $.fs.exists(installed)) {
      const path = installedKinerjaPath(String(await $.fs.read(installed)))
      if (path !== undefined) {
        candidates.push(path)
      }
    }
  }
  for (const candidate of candidates) {
    if (await $.fs.exists(`${candidate}/scripts/kinerja_status.py`)) {
      return candidate
    }
  }
  return undefined
}

async function rootStacks($: EngineInterface): Promise<string[]> {
  const entries = await $.fs.list(hud.cwd).catch(() => [])
  return detectStacks(entries.map(entry => entry.name))
}

async function loadRules(
  $: EngineInterface,
  root: string,
): Promise<{ thresholds: Array<[string, number]>; perFinding: number | undefined } | undefined> {
  const structural = `${root}/rules/quality-score/structural.md`
  if (!(await $.fs.exists(structural))) {
    return undefined
  }
  const thresholds = parseThresholds(String(await $.fs.read(structural)))
  if (thresholds.length === 0) {
    return undefined
  }
  const scoring = `${root}/rules/quality-score.md`
  const perFinding = (await $.fs.exists(scoring))
    ? parsePerFinding(String(await $.fs.read(scoring)))
    : undefined
  return { thresholds, perFinding }
}

async function runStatus($: EngineInterface, root: string): Promise<HudStatus> {
  try {
    const ran = await $.process.run(
      ['python3', `${root}/scripts/kinerja_status.py`, '--json', '--repo', hud.cwd],
      { cwd: hud.cwd, timeoutMs: STATUS_TIMEOUT_MS },
    )
    if (ran.exitCode !== 0) {
      return emptyStatus(`kinerja_status gagal (exit ${ran.exitCode})`)
    }
    return parseStatus(ran.stdout)
  } catch {
    return emptyStatus('kinerja_status tidak bisa dijalankan (python3?)')
  }
}

async function gitOutput($: EngineInterface, args: string[]): Promise<string> {
  const ran = await $.process.run(['git', ...args], { cwd: hud.cwd, timeoutMs: GIT_TIMEOUT_MS })
  return ran.exitCode === 0 ? ran.stdout : `exit ${ran.exitCode}`
}

/** Sidik working tree: diff terhadap HEAD + nama dan mtime file untracked. */
async function diffFingerprint($: EngineInterface): Promise<string> {
  const diff = await gitOutput($, ['diff', 'HEAD', '--no-color', '--no-ext-diff'])
  const untracked = (await gitOutput($, ['ls-files', '--others', '--exclude-standard']))
    .split('\n')
    .filter(name => name !== '')
    .slice(0, MAX_UNTRACKED_STAT)
  const stamps: string[] = []
  for (const name of untracked) {
    const stat = await $.fs.stat(`${hud.cwd}/${name}`).catch(() => undefined)
    stamps.push(`${name}@${stat?.mtimeMs ?? 0}:${stat?.size ?? 0}`)
  }
  return `${diff}\n--untracked--\n${stamps.join('\n')}`
}

/**
 * Pasang HUD untuk folder sesi `cwd`. Dipanggil saat sesi mulai dan setiap kali
 * folder sesi berpindah: desktop app memulai sesi di folder cadangan
 * (`~/.claude/spares/...`) lalu memindahkannya ke folder repo yang dipilih.
 */
async function activate($: EngineInterface, cwd: string): Promise<void> {
  hud.cwd = cwd
  hud.fingerprint = ''
  hud.warnedPushKey = undefined
  hud.kinerjaRoot = hud.kinerjaRoot ?? (await findKinerjaRoot($))
  hud.isActive = hud.kinerjaRoot !== undefined && (await $.fs.exists(`${cwd}/.git`))
  hud.hasStack = hud.isActive && (await rootStacks($)).length > 0
  await update($, status, () => null)
  if (hud.isActive && hud.kinerjaRoot !== undefined) {
    hud.rules = await loadRules($, hud.kinerjaRoot)
    hud.isPaneWanted = true
    refreshInBackground($)
  } else {
    $.ui.status(undefined)
  }
  writeDebugInBackground($)
}

async function followSessionCwd($: EngineInterface): Promise<boolean> {
  const cwd = await $.session.cwd()
  if (cwd === hud.cwd) {
    return false
  }
  await activate($, cwd)
  return true
}

async function pollDiff($: EngineInterface): Promise<void> {
  if (hud.isPolling || hud.running !== undefined) {
    return
  }
  hud.isPolling = true
  try {
    if ((await followSessionCwd($)) || !hud.isActive) {
      return
    }
    // Mode off: tidak menghitung ulang otomatis; /kinerja tetap menghitung.
    if ((await read($, status))?.mode === 'off') {
      return
    }
    if ((await diffFingerprint($)) !== hud.fingerprint) {
      await refresh($)
    }
  } finally {
    hud.isPolling = false
  }
}

function pollInBackground($: EngineInterface): void {
  pollDiff($).catch(() => undefined)
}

async function refresh($: EngineInterface): Promise<HudStatus | null> {
  const root = hud.kinerjaRoot
  if (!hud.isActive || root === undefined) {
    return null
  }
  if (hud.running !== undefined) {
    return hud.running
  }
  hud.running = (async () => {
    const previous = await read($, status)
    hud.fingerprint = await diffFingerprint($).catch(() => '')
    const next = await runStatus($, root)
    hud.lastRefreshAt = await $.clock.now()
    hud.isDirty = false
    if (next.stacks !== null) {
      hud.hasStack = next.stacks.length > 0
    }
    await update($, status, () => next)
    if (next.mode === 'off') {
      $.ui.status(undefined)
      return next
    }
    $.ui.status(statusLineText(next))
    const toast = toastText(newViolations(previous, next))
    if (toast !== undefined) {
      $.ui.toast(toast)
    }
    if (hud.isPaneWanted && hud.hasStack) {
      hud.isPaneWanted = false
      await openPaneForRemoteSurfaces($).catch(() => undefined)
    }
    return next
  })()
  try {
    return await hud.running
  } finally {
    hud.running = undefined
  }
}

// Refresh tanpa ditunggu: kegagalannya (mis. modul di-reload di tengah jalan) diabaikan.
function refreshInBackground($: EngineInterface): void {
  refresh($).catch(() => undefined)
}

async function isPullRequestApproved($: EngineInterface): Promise<boolean> {
  try {
    const ran = await $.process.run(['gh', 'pr', 'view', '--json', 'reviewDecision,state'], {
      cwd: hud.cwd,
      timeoutMs: GH_TIMEOUT_MS,
    })
    if (ran.exitCode !== 0) {
      return false
    }
    const pr = JSON.parse(ran.stdout) as { reviewDecision?: string; state?: string }
    return pr.state === 'OPEN' && pr.reviewDecision === 'APPROVED'
  } catch {
    return false
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    hud.debug.startedAt = new Date(await $.clock.now()).toISOString()
    await $.command.register({
      name: 'kinerja',
      description: 'Prediksi skor Kinerja + pelanggaran diff ini (args: show | hide | panel | debug)',
    })
    await activate($, e.cwd)
    // Satu timer untuk sesi: mengikuti perpindahan folder sesi dan perubahan git diff.
    $.clock.every(POLL_MS, () => pollInBackground($))
    return started
  })

  // Folder sesi berpindah (cd, desktop app memindahkan sesi dari folder cadangan).
  on('classic.CwdChanged', async ($, e, next) => {
    const changed = await next(e)
    if (e.new_cwd !== hud.cwd) {
      await activate($, e.new_cwd).catch(() => undefined)
    }
    return changed
  })

  // Desktop app / VS Code / ponsel yang menyambung setelah sesi mulai.
  on('session.attach', async ($, e, next) => {
    const attached = await next(e)
    if (!hud.debug.surfaces.includes(e.surface)) {
      hud.debug.surfaces = [...hud.debug.surfaces, e.surface]
    }
    if (hud.isActive && hud.hasStack && isRemoteSurface(e.surface)) {
      await openPane($).catch(() => undefined)
    }
    return attached
  })

  on('command.run', { command: 'kinerja' }, async ($, e) => {
    const arg = e.args.trim()
    if (arg === 'hide') {
      await update($, isHidden, () => true)
      return { text: 'Band Kinerja disembunyikan penuh. Ketik /kinerja show untuk menampilkannya lagi.' }
    }
    if (arg === 'show') {
      await update($, isHidden, () => false)
      await update($, isCompact, () => false)
      return { text: 'Band Kinerja ditampilkan.' }
    }
    if (arg === 'debug') {
      await followSessionCwd($).catch(() => false)
      hud.debug.surfaces = [...(await $.session.surfaces())]
      await writeDebug($).catch(() => undefined)
      return { text: debugText() }
    }
    if (arg === 'panel') {
      return { text: `Panel Kinerja: ${await openPane($)}` }
    }
    await followSessionCwd($).catch(() => false)
    if (hud.kinerjaRoot === undefined) {
      return { text: 'HUD Kinerja: plugin venturo-kinerja tidak ditemukan. Pasang venturo-kinerja@venturo-tools atau set VENTURO_KINERJA_ROOT.' }
    }
    if (!hud.isActive) {
      return { text: 'HUD Kinerja: folder sesi ini bukan root repo git.' }
    }
    const fresh = await refresh($)
    if (!hud.hasStack) {
      return { text: 'HUD Kinerja: stack repo ini tidak dikenali (tidak ada go.mod, package.json, composer.json, pyproject.toml/requirements.txt, Package.swift/*.xcodeproj, build.gradle, atau pubspec.yaml di root maupun subfolder app).' }
    }
    if (fresh === null) {
      return { text: 'HUD Kinerja: status belum tersedia.' }
    }
    if (fresh.mode === 'off') {
      return { text: `HUD Kinerja: ${modeLine(fresh)}. Band, panel, dan penahan push tidak aktif.\n${MODE_HINT}` }
    }
    return { text: `${reportText(fresh, REPORT_LIMIT)}\n  ${MODE_HINT}` }
  })

  on('prompt.compose', async ($, e, next) => {
    const composed = await next(e)
    const current = await read($, status)
    if (!hud.isActive || !hud.hasStack || hud.rules === undefined || current === null || current.mode === 'off') {
      return composed
    }
    const text = rulesSection(hud.rules.thresholds, hud.rules.perFinding, current.mode)
    return {
      sections: [...composed.sections, { id: `${PLUGIN}:rules`, text, scope: 'session' as const }],
    }
  })

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (!hud.isActive || ran.deny !== undefined || ran.isError === true) {
      return ran
    }
    const filePath = (e as { file_path?: unknown }).file_path
    const command = (e as { command?: unknown }).command
    const isEdit = EDIT_TOOLS.has(String(e.tool)) && typeof filePath === 'string' && isWatchedFile(filePath)
    const isCommit = String(e.tool) === 'Bash' && typeof command === 'string' && isCommitCommand(command)
    if (isEdit || isCommit) {
      hud.isDirty = true
      if ((await $.clock.now()) - hud.lastRefreshAt >= MIN_REFRESH_GAP_MS) {
        refreshInBackground($)
      }
    }
    return ran
  }).catch(($, e, next) => next(e))

  // Penahan push/PR: fail-open, kegagalan hook ini tidak pernah memblokir.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!hud.isActive || !hud.hasStack || !isPushCommand(e.command)) {
      return next(e)
    }
    const fresh = await refresh($)
    // Hanya mode enforce yang menahan push; advisory/off tidak pernah memblokir.
    if (fresh === null || fresh.error !== null || fresh.mode !== 'enforce') {
      return next(e)
    }
    const blocked = pushBlockReason(fresh)
    if (blocked !== undefined) {
      return { deny: blocked }
    }
    if (isGitPush(e.command) && (await isPullRequestApproved($))) {
      return {
        deny: 'venturo-kinerja-hud: PR untuk branch ini sudah di-approve. Push baru dihitung pelanggaran PR lock di Kinerja dan tidak direview. Konfirmasi ke user dulu; bila perlu perubahan, buat PR baru.',
      }
    }
    const pushKey = `${fresh.head}|${fresh.diffHash}`
    const warning = pushWarning(fresh, PUSH_WARNING_LIMIT)
    if (warning !== undefined && hud.warnedPushKey !== pushKey) {
      hud.warnedPushKey = pushKey
      return { deny: warning }
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const completed = await next(e)
    if (hud.isDirty) {
      refreshInBackground($)
    }
    return completed
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    noteRender($, 'AbovePrompt', e.surface)
    const current = await read($, status)
    const isOff = current?.mode === 'off'
    if (!hud.isActive || !hud.hasStack || current === null || isOff || e.props.hasSurvey || (await read($, isHidden))) {
      return next(e)
    }
    const { Box, Button, Text } = $.ui.resolve(e)
    if (await read($, isCompact)) {
      return (
        <Box>
          <Text dimColor>{statusLineText(current)} </Text>
          <Button key="show" label="Tampilkan" onPress={() => update($, isCompact, () => false)} />
        </Box>
      )
    }
    const expanded = await read($, isExpanded)
    const isBlocked = current.status === 'blocked'
    const color = current.error !== null ? 'subtle' : isBlocked ? 'error' : current.violations.length > 0 ? 'warning' : 'success'
    const room = Math.max(0, Math.min(BAND_LIMIT, e.props.maxRows - 2))
    const gates = failedGates(current)
    const detailCount = current.violations.length + gates.length

    return (
      <Box flexDirection="column">
        <Box>
          <Text color={color}>{summaryLine(current)} </Text>
          {detailCount > 0 && (
            <Button
              key="detail"
              label={expanded ? 'Tutup' : `Detail (${detailCount})`}
              hotkey="k"
              onPress={() => update($, isExpanded, value => !value)}
            />
          )}
          <Button key="compact" label="Ringkas" onPress={() => update($, isCompact, () => true)} />
        </Box>
        {expanded &&
          gates.slice(0, room).map(gate => (
            <Text color="error">
              gate {gate.id}: {gate.detail}
            </Text>
          ))}
        {expanded &&
          current.violations.slice(0, Math.max(0, room - gates.length)).map(v => (
            <Text dimColor>{violationLine(v)}</Text>
          ))}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE_ID }, async ($, e) => {
    noteRender($, 'Pane', e.surface)
    const { Box, Button, Text } = $.ui.resolve(e)
    const current = await read($, status)
    if (current === null) {
      return <Text dimColor>Menghitung prediksi skor Kinerja…</Text>
    }
    if (current.mode === 'off') {
      return <Text dimColor>HUD Kinerja mati untuk repo ini. {MODE_HINT}</Text>
    }
    const gates = failedGates(current)
    const room = Math.max(1, (e.viewport?.rows ?? 30) - 8)
    return (
      <Box flexDirection="column">
        <Text bold>{current.error === null ? `Prediksi ${current.final === null ? '–' : `≈${current.final}`}` : current.error}</Text>
        {current.dimensions.map(dim => (
          <Text>{dimensionText(dim)}</Text>
        ))}
        <Text dimColor>{modeLine(current)}</Text>
        {current.stacks !== null && current.stacks.length > 0 && <Text dimColor>stack: {current.stacks.join(', ')}</Text>}
        {gates.map(gate => (
          <Text color="error">
            gate {gate.id}: {gate.detail}
          </Text>
        ))}
        {current.violations.length === 0 && gates.length === 0 && <Text color="success">Tidak ada pelanggaran statis.</Text>}
        {current.violations.slice(0, Math.min(PANE_LIMIT, room)).map(v => (
          <Text dimColor>{violationLine(v)}</Text>
        ))}
        {current.violations.length > Math.min(PANE_LIMIT, room) && (
          <Text dimColor>… {current.violations.length - Math.min(PANE_LIMIT, room)} pelanggaran lain (/kinerja)</Text>
        )}
        <Button key="refresh" label="Hitung ulang" onPress={() => refreshInBackground($)} />
      </Box>
    )
  })
}
