"""Fixture per bahasa untuk analyzer ambang.

Tiap fixture punya fungsi yang HARUS tertangkap — long_fn (>50 baris), deep
(nesting 5), many (6 parameter), magic (literal 42) — dan yang TIDAK boleh
tertangkap: five (5 parameter), tricky (brace/kata kunci di string & komentar,
objek literal bersarang), serta pasangan generik/destructuring/parameter bernama.
"""

import os

LONG = 52  # baris statement di long_fn → total > 50


def _rep(line, indent):
    return "\n".join(indent + line for _ in range(LONG))


PY = '''import logging

TIMEOUT = 30


def long_fn(a):
    total = 0
{long}
    return total


def deep(xs):
    for row in xs:
        for v in row:
            if v:
                while v > 0:
                    try:
                        v -= 1
                    except ValueError:
                        pass
    return xs


def many(a, b, c, d, e, f):
    return a


class Repo:
    def five(self, a, b, c, d, e):
        return a

    @staticmethod
    def static_five(a, b, c, d, e):
        return a


def magic(n):
    LIMIT = 100
    if n > 42:
        logging.info("over %d", 500)
    return LIMIT


def tricky():
    s = "{{ {{ {{ if ( for"
    d = {{"a": {{"b": {{"c": {{"d": 7}}}}}}}}
    # if if if {{ {{
    return s, d
'''.replace("{long}", _rep("total += a", "    ")).replace("{{", "{").replace("}}", "}")

TS = '''import React from 'react';

const TIMEOUT = 30;

export function longFn(a: number): number {
  let total = 0;
{long}
  return total;
}

export const deep = (xs: number[][]): number => {
  let t = 0;
  for (const row of xs) {
    for (const v of row) {
      if (v) {
        while (v > t) {
          try {
            t++;
          } catch (e) {
            t--;
          }
        }
      }
    }
  }
  return t;
};

export function many(a: number, b: number, c: number, d: number, e: number, f: number) {
  return a;
}

export function destructured({ a, b, c, d, e, f }: Record<string, number>, g: number) {
  return a + b + c + d + e + f + g;
}

class Repo {
  five(a: number, b: number, c: number, d: number, e: number) {
    return a;
  }
}

export function magic(n: number) {
  const LIMIT = 100;
  if (n > 42) {
    console.log('over', 500);
  }
  return LIMIT;
}

export function tricky() {
  const s = '{ { { if ( for';
  const t = `${'}'} { ${TIMEOUT}`;
  const o = { a: { b: { c: { d: 7 } } } };
  // if (x) { {
  return [s, t, o];
}

export function Card() {
  return <div style={{ padding: 16 }}>{[3, 4].map((x) => <span key={x}>{x * 3}</span>)}</div>;
}
'''.replace("{long}", _rep("total += a;", "  "))

JS = TS.replace(": number[][]", "").replace("): number =>", ") =>").replace("): number {", ") {") \
    .replace(": number", "").replace(": Record<string, number>", "").replace("import React from 'react';\n", "")

PHP = '''<?php
namespace App;

class Repo {
    const TIMEOUT = 30;

    public function longFn($a) {
        $total = 0;
{long}
        return $total;
    }

    public function deep(array $xs): int {
        $t = 0;
        foreach ($xs as $row) {
            foreach ($row as $v) {
                if ($v) {
                    while ($v > $t) {
                        try {
                            $t++;
                        } catch (\\Exception $e) {
                            $t--;
                        }
                    }
                }
            }
        }
        return $t;
    }

    public function many($a, $b, $c, $d, $e, $f) {
        return $a;
    }

    public function five($a, $b, $c, $d, $e) {
        return $a;
    }

    public function magic(int $n): int {
        if ($n > 42) {
            error_log("over 500");
        }
        return self::TIMEOUT;
    }

    public function tricky(): array {
        $s = "{ { { if ( for {$this->x} }";
        $t = 'x } {';
        // if ($x) { {
        # foreach { {
        $o = ['a' => ['b' => ['c' => 7]]];
        return [$s, $t, $o];
    }
}
'''.replace("{long}", _rep("$total += $a;", "        "))

SWIFT = '''import Foundation

let timeoutSeconds = 30

struct Repo {
    func longFn(_ a: Int) -> Int {
        var total = 0
{long}
        return total
    }

    func deep(_ xs: [[Int]]) -> Int {
        var t = 0
        for row in xs {
            for v in row {
                if v > 0 {
                    while v > t {
                        if t >= 0 {
                            t += 1
                        }
                    }
                }
            }
        }
        return t
    }

    func many(a: Int, b: Int, c: Int, d: Int, e: Int, f: Int) -> Int {
        return a
    }

    func five(a: Int, b: Int, c: Int, d: Int, e: Int) -> Int {
        return a
    }

    func generic(_ m: Dictionary<String, Int>, _ n: Int) -> Int {
        return n
    }

    func magic(_ n: Int) -> Int {
        if n > 42 {
            print("over \\(500)")
        }
        return 0
    }

    func tricky() -> String {
        let s = "{ { { if ( for \\(["a": 1].count) }"
        // if x { {
        /* if { /* nested { */ { */
        return s
    }
}
'''.replace("{long}", _rep("total += a", "        "))

KOTLIN = '''package app

const val TIMEOUT = 30

class Repo {
    fun longFn(a: Int): Int {
        var total = 0
{long}
        return total
    }

    fun deep(xs: List<List<Int>>): Int {
        var t = 0
        for (row in xs) {
            for (v in row) {
                if (v > 0) {
                    while (v > t) {
                        if (t >= 0) {
                            t++
                        }
                    }
                }
            }
        }
        return t
    }

    fun many(a: Int, b: Int, c: Int, d: Int, e: Int, f: Int): Int {
        return a
    }

    fun five(a: Int, b: Int, c: Int, d: Int, e: Int): Int {
        return a
    }

    fun generic(m: Map<String, Int>, n: Int): Int {
        return n
    }

    fun magic(n: Int): Int {
        if (n > 42) {
            println("over 500")
        }
        return when (n) {
            1 -> 0
            else -> 1
        }
    }

    fun tricky(): String {
        val s = "{ { { if ( for ${mapOf("a" to 1).size} }"
        // if (x) { {
        return s
    }
}
'''.replace("{long}", _rep("total += a", "        "))

DART = '''import 'package:flutter/material.dart';

const timeout = 30;

class Repo {
  int longFn(int a) {
    var total = 0;
{long}
    return total;
  }

  int deep(List<List<int>> xs) {
    var t = 0;
    for (final row in xs) {
      for (final v in row) {
        if (v > 0) {
          while (v > t) {
            if (t >= 0) {
              t++;
            }
          }
        }
      }
    }
    return t;
  }

  int many(int a, int b, int c, int d, int e, int f) {
    return a;
  }

  int five(int a, int b, int c, int d, int e) {
    return a;
  }

  int named(int a, {required int b, int c = 0}) {
    return a + b + c;
  }

  int magic(int n) {
    if (n > 42) {
      print('over 500');
    }
    return 0;
  }

  String tricky() {
    final s = '{ { { if ( for ${{'a': 1}.length} }';
    // if (x) { {
    return s;
  }
}
'''.replace("{long}", _rep("total += a;", "    "))

JAVA = '''package app;

public class Repo {
    private static final int TIMEOUT = 30;

    public int longFn(int a) {
        int total = 0;
{long}
        return total;
    }

    public int deep(int[][] xs) {
        int t = 0;
        for (int[] row : xs) {
            for (int v : row) {
                if (v > 0) {
                    while (v > t) {
                        if (t >= 0) {
                            t++;
                        }
                    }
                }
            }
        }
        return t;
    }

    public int many(int a, int b, int c, int d, int e, int f) {
        return a;
    }

    public int five(int a, int b, int c, int d, int e) {
        return a;
    }

    public int generic(java.util.Map<String, Integer> m, int n) {
        return n;
    }

    public int magic(int n) {
        if (n > 42) {
            System.out.println("over 500");
        }
        return 0;
    }

    public String tricky() {
        String s = "{ { { if ( for";
        // if (x) { {
        return s;
    }
}
'''.replace("{long}", _rep("total += a;", "        "))

FIXTURES = {  # bahasa → (nama file, sumber, nama fungsi per peran)
    "python": ("sample.py", PY, {"long": "long_fn", "deep": "deep", "many": "many", "five": "Repo.five",
                                 "magic": "magic", "tricky": "tricky"}),
    "typescript": ("sample.tsx", TS, {"long": "longFn", "deep": "deep", "many": "many", "five": "Repo.five",
                                      "magic": "magic", "tricky": "tricky"}),
    "javascript": ("sample.jsx", JS, {"long": "longFn", "deep": "deep", "many": "many", "five": "five",
                                      "magic": "magic", "tricky": "tricky"}),
    "php": ("Repo.php", PHP, {"long": "longFn", "deep": "deep", "many": "many", "five": "five",
                              "magic": "magic", "tricky": "tricky"}),
    "swift": ("Repo.swift", SWIFT, {"long": "longFn", "deep": "deep", "many": "many", "five": "five",
                                    "magic": "magic", "tricky": "tricky"}),
    "kotlin": ("Repo.kt", KOTLIN, {"long": "longFn", "deep": "deep", "many": "many", "five": "five",
                                   "magic": "magic", "tricky": "tricky"}),
    "dart": ("repo.dart", DART, {"long": "longFn", "deep": "deep", "many": "many", "five": "five",
                                 "magic": "magic", "tricky": "tricky"}),
    "java": ("Repo.java", JAVA, {"long": "longFn", "deep": "deep", "many": "many", "five": "five",
                                 "magic": "magic", "tricky": "tricky"}),
}

UI_COMPONENTS = {  # bahasa → (nama file, pembuka, baris isi, penutup) untuk file komponen > 300 baris
    "typescript": ("Big.tsx", "export function Big() {\n  return (\n    <div>\n", "      <p>baris</p>\n",
                   "    </div>\n  );\n}\n"),
    "swift": ("BigView.swift", "import SwiftUI\n\nstruct BigView: View {\n    var body: some View {\n        VStack {\n",
              "            Text(\"baris\")\n", "        }\n    }\n}\n"),
    "dart": ("big.dart", "class Big extends StatelessWidget {\n  Widget build(BuildContext context) {\n"
             "    return Column(children: [\n", "      Text('baris'),\n", "    ]);\n  }\n}\n"),
    "kotlin": ("Big.kt", "@Composable\nfun Big() {\n    Column {\n", "        Text(\"baris\")\n", "    }\n}\n"),
    "vue": ("Big.vue", "<template>\n  <div>\n", "    <p>baris</p>\n", "  </div>\n</template>\n"),
}


def write_all(directory):
    """Tulis semua fixture; kembali {bahasa: path}."""
    out = {}
    for lang, (name, src, _) in FIXTURES.items():
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        out[lang] = path
    return out


def write_ui(directory, lang, body_lines=310):
    name, head, line, tail = UI_COMPONENTS[lang]
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(head + line * body_lines + tail)
    return path
