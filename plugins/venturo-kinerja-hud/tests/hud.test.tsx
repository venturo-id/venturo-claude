import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { detectStacks, isWatchedFile, parseStatus, parseThresholds, pushWarning, rulesSection, summaryLine } from '../hooks/lib'

const REPO = '/repo'
const KINERJA = '/plugins/venturo-kinerja'
const STRUCTURAL_MD = [
  '---',
  'weight: 30',
  '---',
  '- function_length: maks 50 — hitung semua baris',
  '- function_complexity: maks 10 — hitung tiap percabangan',
  '- parameter_count: maks 5 — parameter posisional',
].join('\n')
const SCORING_MD = '---\nper_finding: 10\n---\nbody'

type Violation = { file: string; line: number; symbol: string; category: string; detail: string; points_final: number }

function statusJson(options: { violations?: Violation[]; commitOk?: boolean; final?: number } = {}): string {
  const violations = options.violations ?? []
  const commitOk = options.commitOk ?? true
  return JSON.stringify({
    schema_version: 1,
    head: 'abc123',
    diff_hash: `sha256:${violations.length}`,
    changed: { files: 2, lines: 40, go_files: 1 },
    predicted: {
      final: options.final ?? 90,
      status: commitOk ? 'scored' : 'blocked',
      blocked_by: commitOk ? [] : ['commit_format'],
      source: 'static',
      dimensions: {
        bug: { score: null, skipped: true, weight: 30, findings: 0 },
        structural: { score: 100 - 10 * violations.length, skipped: false, weight: 30, findings: violations.length },
        readability: { score: 100, skipped: false, weight: 30, findings: 0 },
        doc_sync: { score: null, skipped: true, weight: 10, findings: 0 },
      },
    },
    violations,
    gates: [
      { id: 'commit_format', ok: commitOk, effect: 'unscored', detail: commitOk ? 'ok' : '1 masalah format commit' },
      { id: 'rules_fresh', ok: true, effect: 'info', detail: 'rules disync 0.0 hari lalu' },
    ],
    rules: { age_days: 0, stale: false },
  })
}

const LONG_FUNC: Violation = {
  file: 'internal/user.service.go',
  line: 40,
  symbol: 'UserService.Create',
  category: 'oversized-function',
  detail: 'fungsi 63 baris > 50',
  points_final: 3,
}

const KINERJA_COMMAND = {
  command: 'kinerja',
  args: '',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: false, columns: 100 },
} as const

const BAND = {
  plugin: 'venturo-kinerja-hud',
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 12,
    bodyColumns: 100,
    scroll: { offset: 0, bodyRows: 12 },
    view: {},
    title: '',
    isFocused: false,
  },
} as const

type World = {
  status: () => string
  diff?: () => string
  rootNames?: string[]
  ghApproved?: boolean
  surfaces?: string[]
  cwd?: () => string
}

// Dunia di bawah plugin: plugin venturo-kinerja bersebelahan via env, repo Go, status dari `world`.
function stubWorld(
  on: On,
  world: World,
): { toasts: string[]; runs: string[][]; clock: ReturnType<typeof mock.clock>; opened: string[]; writes: Record<string, string> } {
  const opened: string[] = []
  const writes: Record<string, string> = {}
  const toasts: string[] = []
  const runs: string[][] = []
  mock.env(on, { VENTURO_KINERJA_ROOT: KINERJA, HOME: '/home/dev' })
  const clock = mock.clock(on, { now: 100_000 })
  on('command.register', () => ({ value: { command: 'kinerja' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('fs.exists', (_, e) => {
    const exists =
      e.path === `${KINERJA}/scripts/kinerja_status.py` ||
      e.path === `${KINERJA}/rules/quality-score/structural.md` ||
      e.path === `${KINERJA}/rules/quality-score.md` ||
      e.path === `${REPO}/.git`
    return { value: exists }
  })
  on('fs.list', () => ({
    value: (world.rootNames ?? ['go.mod', 'main.go']).map(name => ({
      name,
      kind: 'file' as const,
      size: 0,
      mtimeMs: 0,
      isLink: false,
    })),
  }))
  on('fs.read', (_, e) => ({ value: e.path.endsWith('structural.md') ? STRUCTURAL_MD : SCORING_MD }))
  on('process.run', (_, e) => {
    runs.push([...e.argv])
    if (e.argv[0] === 'git') {
      const out = e.argv[1] === 'diff' ? (world.diff?.() ?? '') : ''
      return { value: { exitCode: 0, stdout: out, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    }
    if (e.argv[0] === 'gh') {
      const pr = world.ghApproved === true ? { state: 'OPEN', reviewDecision: 'APPROVED' } : { state: 'OPEN', reviewDecision: '' }
      return { value: { exitCode: 0, stdout: JSON.stringify(pr), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    }
    return { value: { exitCode: 0, stdout: world.status(), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.toast', (_, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.status', () => ({ value: undefined }))
  on('session.cwd', () => ({ value: world.cwd?.() ?? REPO }))
  on('session.surfaces', () => ({ value: (world.surfaces ?? ['terminal']) as Array<'terminal' | 'desktop' | 'vscode' | 'mobile'> }))
  on('ui.open', (_, e) => {
    opened.push(e.id)
    return { value: { isPlaced: true as const } }
  })
  on('fs.write', (_, e) => {
    writes[e.path] = e.text
    return { value: undefined }
  })
  on('tool.call', () => ({ result: {} }))
  return { toasts, runs, clock, opened, writes }
}

describe('lib', () => {
  test('parseStatus membaca kontrak schema 1', async () => {
    const status = parseStatus(statusJson({ violations: [LONG_FUNC], final: 87 }))
    expect(status.final).toBe(87)
    expect(status.violations[0]?.points).toBe(3)
    expect(summaryLine(status)).toBe('Kinerja ≈87 · Bug – · Struktur 90 (1) · Baca 100 · Doc –')
  })

  test('schema lain ditolak dengan pesan, bukan crash', async () => {
    expect(parseStatus('{"schema_version": 2}').error).toBe('schema_version 2 tidak didukung HUD')
    expect(parseStatus('bukan json').error).toBe('output kinerja_status bukan JSON')
  })

  test('ambang dibaca dari rule structural', async () => {
    expect(parseThresholds(STRUCTURAL_MD)).toEqual([
      ['function_length', 50],
      ['function_complexity', 10],
      ['parameter_count', 5],
    ])
    expect(rulesSection(parseThresholds(STRUCTURAL_MD), 10)).toContain('(−10 per temuan di dimensinya): function_length ≤ 50')
  })

  test('stack dikenali dari manifest di root', async () => {
    expect(detectStacks(['package.json', 'src', 'tsconfig.json'])).toEqual(['javascript'])
    expect(detectStacks(['App.xcodeproj', 'Podfile', 'composer.json'])).toEqual(['php', 'swift'])
    expect(detectStacks(['requirements-dev.txt', 'build.gradle.kts', 'pubspec.yaml'])).toEqual(['python', 'kotlin', 'dart'])
    expect(detectStacks(['README.md'])).toEqual([])
  })

  test('file yang dipantau mencakup semua bahasa yang didukung', async () => {
    for (const path of ['src/App.tsx', 'app/Http/Controllers/A.php', 'api/main.py', 'Sources/View.swift', 'lib/a.dart', 'x.kt', 'package.json']) {
      expect(isWatchedFile(path)).toBe(true)
    }
    expect(isWatchedFile('assets/logo.png')).toBe(false)
  })

  test('tanpa pelanggaran tidak ada peringatan push', async () => {
    expect(pushWarning(parseStatus(statusJson()), 5)).toBeUndefined()
  })
})

describe('mod', () => {
  test('band menampilkan prediksi dan detail pelanggaran di setiap surface', async ($, on) => {
    stubWorld(on, { status: () => statusJson({ violations: [LONG_FUNC], final: 87 }) })
    await $.session.start({ cwd: REPO, surface: 'desktop', isInteractive: true })
    await $.command.run(KINERJA_COMMAND)

    for (const surface of ['terminal', 'desktop', 'vscode'] as const) {
      const ui = await $.ui.mount({ ...BAND, surface })
      expect((await ui.find({ type: 'Text', text: /Kinerja ≈87/ }))?.text).toBe(
        'Kinerja ≈87 · Bug – · Struktur 90 (1) · Baca 100 · Doc – ',
      )
      await ui.press({ key: 'detail' })
      expect(await ui.find({ type: 'Text', text: /oversized-function UserService.Create/ })).toBeDefined()
      await ui.press({ key: 'detail' })
      await ui.unmount()
    }
  })

  test('repo tanpa stack dikenali: band diserahkan ke engine', async ($, on) => {
    stubWorld(on, { status: statusJson, rootNames: ['README.md', 'Makefile'] })
    on('ui.render', ($, e) => {
      const { Text } = $.ui.resolve(e)
      return <Text>engine</Text>
    })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
    await ui.unmount()
  })

  test('/kinerja melaporkan gate dan pelanggaran', async ($, on) => {
    stubWorld(on, { status: () => statusJson({ violations: [LONG_FUNC], commitOk: false }) })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const result = await $.command.run(KINERJA_COMMAND)
    expect(result.text).toContain('⛔ tidak dinilai: format commit')
    expect(result.text).toContain('gate format commit: 1 masalah format commit')
    expect(result.text).toContain('−3 oversized-function UserService.Create internal/user.service.go:40')
  })

  test('section ringkasan ambang ditambahkan ke system prompt', async ($, on) => {
    stubWorld(on, { status: statusJson })
    on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'intro', scope: 'shared' }] }))
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    await $.command.run(KINERJA_COMMAND)
    const composed = await $.prompt.compose({
      model: 'claude-opus-5-5',
      promptModel: 'claude-opus-5-5',
      surfaces: ['terminal'],
      tools: [],
      outputStyle: null,
      traits: [],
    })
    const section = composed.sections.find(one => one.id === 'venturo-kinerja-hud:rules')
    expect(section?.scope).toBe('session')
    expect(section?.text).toContain('function_length ≤ 50, function_complexity ≤ 10, parameter_count ≤ 5')
  })

  test('push ditahan bila gate commit gagal', async ($, on) => {
    stubWorld(on, { status: () => statusJson({ commitOk: false }) })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const pushed = await $.tool.call({ tool: 'Bash', command: 'git push origin feat/x' })
    expect(pushed.deny).toContain('push ditahan')
  })

  test('pelanggaran: push diperingatkan sekali, lalu diloloskan', async ($, on) => {
    stubWorld(on, { status: () => statusJson({ violations: [LONG_FUNC] }) })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const first = await $.tool.call({ tool: 'Bash', command: 'git push' })
    expect(first.deny).toContain('tanyakan apakah tetap push')
    const second = await $.tool.call({ tool: 'Bash', command: 'git push' })
    expect(second.deny).toBeUndefined()
  })

  test('PR yang sudah di-approve: push ditahan (PR lock)', async ($, on) => {
    stubWorld(on, { status: statusJson, ghApproved: true })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const pushed = await $.tool.call({ tool: 'Bash', command: 'git push' })
    expect(pushed.deny).toContain('PR lock')
  })

  test('pelanggaran baru setelah edit memunculkan toast', async ($, on) => {
    let current = statusJson()
    const world = stubWorld(on, { status: () => current })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    await $.command.run(KINERJA_COMMAND)
    current = statusJson({ violations: [LONG_FUNC] })
    await $.tool.call({ tool: 'Write', file_path: `${REPO}/internal/user.service.go`, content: 'package user' })
    await $.command.run(KINERJA_COMMAND)
    expect(world.toasts).toContain(
      'Kinerja: −3 oversized-function UserService.Create internal/user.service.go:40 — fungsi 63 baris > 50',
    )
  })

  test('edit manual di luar Claude tertangkap polling git diff', async ($, on) => {
    let current = statusJson()
    let diff = 'diff --git a/x.go b/x.go'
    const world = stubWorld(on, { status: () => current, diff: () => diff })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    await world.clock.settle()
    const statusRuns = () => world.runs.filter(argv => argv[0] === 'python3').length
    const before = statusRuns()

    await world.clock.advance(8_000)
    expect(statusRuns()).toBe(before)

    current = statusJson({ violations: [LONG_FUNC] })
    diff = 'diff --git a/x.go b/x.go\n+func Long() {}'
    await world.clock.advance(8_000)
    expect(statusRuns()).toBe(before + 1)
    expect(world.toasts).toContain(
      'Kinerja: −3 oversized-function UserService.Create internal/user.service.go:40 — fungsi 63 baris > 50',
    )
  })

  test('repo React (package.json) aktif dan menampilkan stack', async ($, on) => {
    const withStacks = () =>
      JSON.stringify({
        ...JSON.parse(statusJson()),
        stacks: [
          { id: 'react', language: 'typescript', framework: 'nextjs', rules: ['react'] },
          { id: 'php', language: 'php', framework: null, rules: ['php'] },
        ],
      })
    stubWorld(on, { status: withStacks, rootNames: ['package.json', 'src'] })
    await $.session.start({ cwd: REPO, surface: 'desktop', isInteractive: true })
    const result = await $.command.run(KINERJA_COMMAND)
    expect(result.text).toContain('stack: react (nextjs), php')
    const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
    expect(await ui.find({ type: 'Text', text: /Kinerja ≈90/ })).toBeDefined()
    await ui.unmount()
  })

  test('monorepo tanpa manifest di root: aktif karena kinerja_status menemukan stack di subfolder', async ($, on) => {
    const sub = () => JSON.stringify({ ...JSON.parse(statusJson()), stacks: [{ id: 'node', framework: 'express' }] })
    stubWorld(on, { status: sub, rootNames: ['apps', 'README.md'] })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const result = await $.command.run(KINERJA_COMMAND)
    expect(result.text).toContain('stack: node (express)')
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    expect(await ui.find({ type: 'Text', text: /Kinerja ≈90/ })).toBeDefined()
    await ui.unmount()
  })

  test('kinerja_status melaporkan stacks kosong: band disembunyikan', async ($, on) => {
    const noStack = () => JSON.stringify({ ...JSON.parse(statusJson()), stacks: [] })
    stubWorld(on, { status: noStack, rootNames: ['package.json'] })
    on('ui.render', ($, e) => {
      const { Text } = $.ui.resolve(e)
      return <Text>engine</Text>
    })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    await $.command.run(KINERJA_COMMAND)
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
    await ui.unmount()
  })

  test('Ringkas: band jadi satu baris dengan tombol Tampilkan, lalu kembali penuh', async ($, on) => {
    stubWorld(on, { status: () => statusJson({ violations: [LONG_FUNC], final: 87 }) })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    await $.command.run(KINERJA_COMMAND)
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    await ui.press({ key: 'compact' })
    expect((await ui.find({ type: 'Text', text: /kinerja ≈87/ }))?.text).toBe('kinerja ≈87 ')
    expect(await ui.find({ key: 'show' })).toBeDefined()
    await ui.press({ key: 'show' })
    expect(await ui.find({ type: 'Text', text: /Kinerja ≈87 · Bug/ })).toBeDefined()
    await ui.unmount()
  })

  test('/kinerja hide memberi tahu cara menampilkan lagi', async ($, on) => {
    stubWorld(on, { status: statusJson })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const hidden = await $.command.run({ ...KINERJA_COMMAND, args: 'hide' })
    expect(hidden.text).toContain('/kinerja show')
  })

  test('surface desktop: panel Kinerja dibuka otomatis dan digambar', async ($, on) => {
    const world = stubWorld(on, { status: () => statusJson({ violations: [LONG_FUNC], final: 87 }), surfaces: ['desktop'] })
    await $.session.start({ cwd: REPO, surface: 'desktop', isInteractive: true })
    await $.command.run(KINERJA_COMMAND)
    expect(world.opened).toContain('kinerja')
    const pane = await $.ui.mount({
      plugin: 'venturo-kinerja-hud',
      component: 'Pane',
      requestId: 'kinerja',
      surface: 'desktop',
      props: { title: 'Kinerja', isFocused: false, bodyColumns: 50, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} },
    })
    expect((await pane.find({ type: 'Text', text: /Prediksi/ }))?.text).toBe('Prediksi ≈87')
    expect(await pane.find({ type: 'Text', text: /oversized-function UserService.Create/ })).toBeDefined()
    await pane.unmount()
    const debug = world.writes[`${REPO}/.claude/venturo-kinerja/hud-debug.json`]
    expect(debug).toContain('"Pane@desktop": 1')
  })

  test('surface terminal: panel tidak dibuka otomatis; /kinerja debug melaporkan keadaan', async ($, on) => {
    const world = stubWorld(on, { status: statusJson })
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    expect(world.opened).toHaveLength(0)
    const debug = await $.command.run({ ...KINERJA_COMMAND, args: 'debug' })
    expect(debug.text).toContain('surface terpasang: terminal')
    expect(world.writes[`${REPO}/.claude/venturo-kinerja/.gitignore`]).toBe('*\n')
  })

  test('desktop: sesi mulai di folder cadangan lalu pindah ke repo, HUD ikut aktif', async ($, on) => {
    const SPARE = '/home/dev/.claude/spares/spare-abc'
    let cwd = SPARE
    const world = stubWorld(on, {
      status: () => statusJson({ violations: [LONG_FUNC], final: 87 }),
      surfaces: ['desktop'],
      cwd: () => cwd,
    })
    await $.session.start({ cwd: SPARE, surface: 'desktop', isInteractive: true })
    await world.clock.settle()
    const before = await $.command.run({ ...KINERJA_COMMAND, args: 'debug' })
    expect(before.text).toContain('aktif: false')

    cwd = REPO
    await world.clock.advance(8_000)
    const after = await $.command.run({ ...KINERJA_COMMAND, args: 'debug' })
    expect(after.text).toContain(`cwd: ${REPO}`)
    expect(after.text).toContain('aktif: true · stack dikenali: true')
    expect(world.opened).toContain('kinerja')
    const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
    expect(await ui.find({ type: 'Text', text: /Kinerja ≈87/ })).toBeDefined()
    await ui.unmount()
  })

  const withMode = (json: string, value: string, source = 'default') =>
    JSON.stringify({ ...JSON.parse(json), mode: { value, source } })

  test('mode saran: band berlabel saran, push tidak pernah ditahan, prompt tidak memaksa format commit', async ($, on) => {
    stubWorld(on, { status: () => withMode(statusJson({ violations: [LONG_FUNC], commitOk: false, final: 87 }), 'advisory') })
    on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'intro', scope: 'shared' }] }))
    await $.session.start({ cwd: REPO, surface: 'terminal', isInteractive: true })
    const report = await $.command.run(KINERJA_COMMAND)
    expect(report.text).toContain('mode: saran (estimasi saja, tidak ada yang diblokir) — dari default repo non-Venturo')
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    expect(await ui.find({ type: 'Text', text: /^Kinerja \(saran\) ≈87/ })).toBeDefined()
    await ui.unmount()
    const pushed = await $.tool.call({ tool: 'Bash', command: 'git push' })
    expect(pushed.deny).toBeUndefined()
    const composed = await $.prompt.compose({
      model: 'claude-opus-5-5',
      promptModel: 'claude-opus-5-5',
      surfaces: ['terminal'],
      tools: [],
      outputStyle: null,
      traits: [],
    })
    const section = composed.sections.find(one => one.id === 'venturo-kinerja-hud:rules')
    expect(section?.text).toContain('TIDAK diwajibkan')
    expect(section?.text).not.toContain('[KODE-123]')
  })

  test('mode off: band, panel, dan section prompt tidak ada; /kinerja menjelaskan cara menyalakan', async ($, on) => {
    const world = stubWorld(on, { status: () => withMode(statusJson({ violations: [LONG_FUNC] }), 'off', 'git-config'), surfaces: ['desktop'] })
    on('ui.render', ($, e) => {
      const { Text } = $.ui.resolve(e)
      return <Text>engine</Text>
    })
    await $.session.start({ cwd: REPO, surface: 'desktop', isInteractive: true })
    const report = await $.command.run(KINERJA_COMMAND)
    expect(report.text).toContain('mode: mati — dari git config kinerja.mode')
    expect(report.text).toContain('git config kinerja.mode enforce|advisory|off')
    expect(world.opened).toHaveLength(0)
    const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
    expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
    await ui.unmount()
  })
})
