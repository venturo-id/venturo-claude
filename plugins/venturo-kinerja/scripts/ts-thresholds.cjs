#!/usr/bin/env node
// ts-thresholds.cjs — metrik ambang struktur TS/JS lewat TypeScript compiler
// API milik project (node_modules/typescript). Tanpa dependency lain.
//
// stdin : {"typescript": "/proj/node_modules/typescript", "files": ["/abs/a.tsx", ...]}
// stdout: {"files": [{path, lines, functions, magic, ui_component, error}]}
//
// Dipanggil thresholds.py; finalisasi pelanggaran dilakukan di sana supaya
// semua bahasa memakai aturan yang sama. Definisi metrik:
//   - fungsi yang diukur = deklarasi bernama: function, method, constructor,
//     accessor, dan arrow/function expression yang di-assign ke variabel,
//     properti objek, atau properti kelas. Callback anonim ikut fungsi induk.
//   - panjang: baris awal deklarasi (setelah decorator) sampai `}` penutup.
//   - kompleksitas: if, ternary, for/for-in/for-of/while/do, case, && dan ||.
//   - nesting: if/loop/switch/try dan callback anonim menambah satu level;
//     `else if` tidak. JSX tidak dihitung.
//   - parameter: jumlah parameter (destructuring = 1), tanpa `this`.
//   - magic: literal angka selain 0/1/2 di badan fungsi, kecuali di atribut
//     JSX, nilai properti objek, const NAMA_KAPITAL, enum, tipe literal, dan
//     argumen console/logger/Error.
'use strict';

const fs = require('fs');
const path = require('path');

function readStdin() {
  return JSON.parse(fs.readFileSync(0, 'utf8'));
}

function scriptKind(ts, file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === '.tsx') return ts.ScriptKind.TSX;
  if (ext === '.ts' || ext === '.mts' || ext === '.cts') return ts.ScriptKind.TS;
  return ts.ScriptKind.JSX; // .js/.jsx/.mjs/.cjs boleh berisi JSX
}

function countLines(src) {
  if (!src) return 0;
  return src.split('\n').length - (src.endsWith('\n') ? 1 : 0);
}

function makeAnalyzer(ts, sf) {
  const line = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
  const K = ts.SyntaxKind;
  const LOOPS = new Set([K.ForStatement, K.ForInStatement, K.ForOfStatement, K.WhileStatement, K.DoStatement]);

  function isFunctionLike(n) {
    return ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n) || ts.isConstructorDeclaration(n) ||
      ts.isGetAccessorDeclaration(n) || ts.isSetAccessorDeclaration(n) || ts.isArrowFunction(n) ||
      ts.isFunctionExpression(n);
  }

  // Nama untuk fungsi "bernama"; undefined = callback anonim (ikut induk).
  function nameOf(n) {
    const named = (n.name && n.name.getText(sf)) || undefined;
    if (ts.isFunctionDeclaration(n)) return named || 'default';
    if (ts.isConstructorDeclaration(n)) return className(n) + '.constructor';
    if (ts.isMethodDeclaration(n) || ts.isGetAccessorDeclaration(n) || ts.isSetAccessorDeclaration(n)) {
      const owner = className(n);
      return owner ? owner + '.' + named : named;
    }
    const p = n.parent;
    if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
    if (ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p)) {
      const owner = ts.isPropertyDeclaration(p) ? className(p) : '';
      const key = p.name.getText(sf);
      return owner ? owner + '.' + key : key;
    }
    if (ts.isExportAssignment(p)) return 'default';
    return undefined;
  }

  function className(n) {
    const c = n.parent;
    return c && (ts.isClassDeclaration(c) || ts.isClassExpression(c)) && c.name ? c.name.text : '';
  }

  function startLine(n) {
    const p = n.parent;
    if ((ts.isArrowFunction(n) || ts.isFunctionExpression(n)) && p && (ts.isVariableDeclaration(p) ||
        ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p))) {
      return line(p.getStart(sf));
    }
    const mods = ts.canHaveModifiers && ts.canHaveModifiers(n) ? ts.getModifiers(n) : undefined;
    const first = mods && mods.length ? mods[0] : null; // export/async, bukan decorator
    return line(first ? first.getStart(sf) : n.getStart(sf));
  }

  // Jalan di badan fungsi tanpa masuk ke fungsi bernama lain.
  function walkOwn(body, visit) {
    function rec(n, depth) {
      if (n !== body && isFunctionLike(n) && nameOf(n)) return;
      const next = visit(n, depth);
      ts.forEachChild(n, (c) => rec(c, next === undefined ? depth : next));
    }
    rec(body, 0);
  }

  function complexity(body) {
    let n = 0;
    walkOwn(body, (node) => {
      if (ts.isIfStatement(node) || ts.isConditionalExpression(node) || LOOPS.has(node.kind) ||
          ts.isCaseClause(node)) n++;
      if (ts.isBinaryExpression(node) && (node.operatorToken.kind === K.AmpersandAmpersandToken ||
          node.operatorToken.kind === K.BarBarToken)) n++;
      return undefined;
    });
    return n;
  }

  function nesting(body) {
    let max = 0;
    function rec(n, depth) {
      if (n !== body && isFunctionLike(n)) {
        if (nameOf(n)) return; // fungsi bernama diukur sendiri
        return block(n.body, depth + 1);
      }
      if (ts.isIfStatement(n)) return ifChain(n, depth);
      if (LOOPS.has(n.kind)) return block(n.statement, depth + 1);
      if (ts.isSwitchStatement(n)) return block(n.caseBlock, depth + 1);
      if (ts.isTryStatement(n)) {
        block(n.tryBlock, depth + 1);
        if (n.catchClause) block(n.catchClause.block, depth + 1);
        if (n.finallyBlock) block(n.finallyBlock, depth + 1);
        return;
      }
      ts.forEachChild(n, (c) => rec(c, depth));
    }
    function block(n, depth) {
      if (!n) return;
      if (depth > max) max = depth;
      rec(n, depth);
    }
    function ifChain(n, depth) {
      rec(n.expression, depth);
      block(n.thenStatement, depth + 1);
      if (n.elseStatement && ts.isIfStatement(n.elseStatement)) ifChain(n.elseStatement, depth);
      else block(n.elseStatement, depth + 1);
    }
    ts.forEachChild(body, (c) => rec(c, 0));
    return max;
  }

  function exemptMagic(n) {
    for (let p = n.parent; p; p = p.parent) {
      if (ts.isJsxAttribute(p) || ts.isJsxExpression(p) || ts.isEnumMember(p) || ts.isLiteralTypeNode(p)) return true;
      if (ts.isPropertyAssignment(p) && p.initializer && n.pos >= p.initializer.pos) return true;
      if (ts.isVariableDeclaration(p) && ts.isIdentifier(p.name) && /^[A-Z][A-Z0-9_]*$/.test(p.name.text)) return true;
      if ((ts.isCallExpression(p) || ts.isNewExpression(p)) && /^(console\.|logger\.|log\.|\w*Error$)/.test(p.expression.getText(sf))) return true;
      if (isFunctionLike(p) || ts.isBlock(p) && isFunctionLike(p.parent)) return false;
    }
    return false;
  }

  function magic(body, out) {
    walkOwn(body, (n) => {
      if (ts.isNumericLiteral(n) && !['0', '1', '2', '0.0', '1.0'].includes(n.text) && !exemptMagic(n)) {
        out.push({ line: line(n.getStart(sf)), value: n.getText(sf) });
      }
      return undefined;
    });
  }

  function analyze() {
    const functions = [];
    const magicHits = [];
    function visit(n) {
      if (isFunctionLike(n) && n.body) {
        const name = nameOf(n);
        if (name) {
          const start = startLine(n);
          const end = line(n.end);
          functions.push({
            name, start, end, lines: end - start + 1,
            complexity: complexity(n.body), nesting: nesting(n.body),
            params: n.parameters.filter((p) => p.name.getText(sf) !== 'this').length,
          });
          magic(n.body, magicHits);
        }
      }
      ts.forEachChild(n, visit);
    }
    visit(sf);
    return { functions, magic: magicHits };
  }

  return analyze;
}

function main() {
  const input = readStdin();
  const ts = require(input.typescript);
  const files = input.files.map((file) => {
    const ui = ['.tsx', '.jsx'].includes(path.extname(file).toLowerCase());
    try {
      const src = fs.readFileSync(file, 'utf8');
      const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, scriptKind(ts, file));
      const res = makeAnalyzer(ts, sf)();
      const diags = sf.parseDiagnostics || [];
      return { path: file, lines: countLines(src), functions: res.functions, magic: res.magic, ui_component: ui,
        error: diags.length ? 'parse: ' + ts.flattenDiagnosticMessageText(diags[0].messageText, ' ') : null };
    } catch (err) {
      return { path: file, lines: 0, functions: [], magic: [], ui_component: ui, error: String(err && err.message || err) };
    }
  });
  process.stdout.write(JSON.stringify({ files }));
}

main();
