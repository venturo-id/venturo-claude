package main

import (
	"fmt"
	"go/ast"
	"go/token"
	"strings"
)

func newViolation(file string, line int, symbol, key string, value, max int, format string) Violation {
	return Violation{
		File: file, Line: line, Symbol: symbol, Key: key, Category: thresholdCategory[key],
		Value: value, Max: max, Detail: fmt.Sprintf(format, value, max),
	}
}

func funcViolations(file string, m FuncMetric, th map[string]int) []Violation {
	checks := []struct {
		key    string
		value  int
		format string
	}{
		{"function_length", m.Lines, "fungsi %d baris > %d"},
		{"function_complexity", m.Complexity, "kompleksitas %d cabang > %d"},
		{"nesting_depth", m.Nesting, "nesting %d level > %d"},
		{"parameter_count", m.Params, "%d parameter > %d"},
	}
	out := []Violation{}
	for _, c := range checks {
		max, ok := th[c.key]
		if ok && c.value > max {
			out = append(out, newViolation(file, m.Start, m.Name, c.key, c.value, max, c.format))
		}
	}
	return out
}

// allowedLiterals tidak dianggap magic value: nilai identitas/indeks yang
// hampir selalu jelas dari konteksnya.
var allowedLiterals = map[string]bool{"0": true, "1": true, "2": true, "0.0": true, "1.0": true}

// exemptCallPrefixes: literal di argumen panggilan log/error tidak dihitung
// (context: "literal di test, config, atau pesan log/error TIDAK dihitung").
var exemptCallPrefixes = []string{"fmt.Errorf", "errors.", "log.", "logger.", "slog.", "panic"}

func magicViolations(fset *token.FileSet, t Target, fn *ast.FuncDecl, symbol string, th map[string]int, all bool) []Violation {
	max, ok := th["magic_values"]
	if !ok {
		return nil
	}
	out := []Violation{}
	seenLine := map[int]bool{}
	ast.Inspect(fn.Body, func(n ast.Node) bool {
		switch x := n.(type) {
		case *ast.GenDecl:
			return x.Tok != token.CONST // konstanta bernama = perbaikan, bukan pelanggaran
		case *ast.CallExpr:
			return !isExemptCall(x)
		case *ast.BasicLit:
			if x.Kind != token.INT && x.Kind != token.FLOAT {
				return true
			}
			line := fset.Position(x.Pos()).Line
			if allowedLiterals[x.Value] || seenLine[line] || !(all || t.touches(line, line)) {
				return true
			}
			seenLine[line] = true
			v := newViolation(t.Path, line, symbol, "magic_values", 1, max, "literal tanpa nama")
			v.Heuristic = true
			v.Detail = fmt.Sprintf("literal %s tanpa nama di logika inti", x.Value)
			out = append(out, v)
		}
		return true
	})
	return out
}

func isExemptCall(call *ast.CallExpr) bool {
	name := exprName(call.Fun)
	for _, p := range exemptCallPrefixes {
		if strings.HasPrefix(name, p) {
			return true
		}
	}
	return false
}

func exprName(e ast.Expr) string {
	switch x := e.(type) {
	case *ast.Ident:
		return x.Name
	case *ast.SelectorExpr:
		return exprName(x.X) + "." + x.Sel.Name
	}
	return ""
}
