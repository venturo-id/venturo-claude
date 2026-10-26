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
  isWatchedFile,
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

// State sesi modul; register dijalankan ulang (dan state ini mulai dari awal) setiap reload.
const hud = {
  cwd: '',
  kinerjaRoot: undefined as string | undefined,
  isActive: false,
  rulesText: undefined as string | undefined,
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

async function loadRulesText($: EngineInterface, root: string): Promise<string | undefined> {
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
  return rulesSection(thresholds, perFinding)
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

async function pollDiff($: EngineInterface): Promise<void> {
  if (!hud.isActive || hud.isPolling || hud.running !== undefined) {
    return
  }
  hud.isPolling = true
  try {
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
    $.ui.status(statusLineText(next))
    const toast = toastText(newViolations(previous, next))
    if (toast !== undefined) {
      $.ui.toast(toast)
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
    hud.cwd = e.cwd
    await $.command.register({
      name: 'kinerja',
      description: 'Prediksi skor Kinerja + pelanggaran diff ini (args: show | hide)',
    })
    hud.kinerjaRoot = await findKinerjaRoot($)
    hud.isActive = hud.kinerjaRoot !== undefined && (await $.fs.exists(`${hud.cwd}/.git`))
    hud.hasStack = hud.isActive && (await rootStacks($)).length > 0
    if (hud.isActive && hud.kinerjaRoot !== undefined) {
      hud.rulesText = await loadRulesText($, hud.kinerjaRoot)
      refreshInBackground($)
      $.clock.every(POLL_MS, () => pollInBackground($))
    }
    return started
  })

  on('command.run', { command: 'kinerja' }, async ($, e) => {
    const arg = e.args.trim()
    if (arg === 'hide' || arg === 'show') {
      await update($, isHidden, () => arg === 'hide')
      return { text: arg === 'hide' ? 'HUD Kinerja disembunyikan.' : 'HUD Kinerja ditampilkan.' }
    }
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
    return { text: fresh === null ? 'HUD Kinerja: status belum tersedia.' : reportText(fresh, REPORT_LIMIT) }
  })

  on('prompt.compose', async ($, e, next) => {
    const composed = await next(e)
    if (!hud.isActive || !hud.hasStack || hud.rulesText === undefined) {
      return composed
    }
    return {
      sections: [...composed.sections, { id: `${PLUGIN}:rules`, text: hud.rulesText, scope: 'session' as const }],
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
    if (fresh === null || fresh.error !== null) {
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
    const current = await read($, status)
    if (!hud.isActive || !hud.hasStack || current === null || e.props.hasSurvey || (await read($, isHidden))) {
      return next(e)
    }
    const { Box, Button, Text } = $.ui.resolve(e)
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
          <Button key="hide" label="Sembunyikan" onPress={() => update($, isHidden, () => true)} />
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
}
