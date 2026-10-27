package main

import (
	"bytes"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"strings"
)

// Definisi metrik mengikuti teks context quality-score/structural (v2):
//   - function_length: baris dari `func` sampai `}` penutup, TERMASUK baris
//     kosong dan komentar di dalamnya (doc comment di atas signature tidak).
//   - function_complexity: tiap percabangan dihitung satu — if/else if,
//     case non-default, for/range, && / ||. Tanpa basis +1.
//   - nesting_depth: badan fungsi = level 0; tiap if/for/switch/select dan
//     func literal di dalam blok menambah satu level; `else if` tidak.
//   - parameter_count: parameter posisional; receiver tidak dihitung.
//   - file_length: semua baris file.
//   - magic_values: literal angka di badan fungsi selain 0, 1, 2 (heuristik;
//     tidak berlaku untuk _test.go; literal string tidak diperiksa).

type FuncMetric struct {
	Name       string `json:"name"`
	Start      int    `json:"start"`
	End        int    `json:"end"`
	Lines      int    `json:"lines"`
	Complexity int    `json:"complexity"`
	Nesting    int    `json:"nesting"`
	Params     int    `json:"params"`
	Touched    bool   `json:"touched"`
}

type Violation struct {
	File      string `json:"file"`
	Line      int    `json:"line"`
	Symbol    string `json:"symbol"`
	Key       string `json:"key"`
	Category  string `json:"category"`
	Value     int    `json:"value"`
	Max       int    `json:"max"`
	Heuristic bool   `json:"heuristic,omitempty"`
	Detail    string `json:"detail"`
}

type FileReport struct {
	Path       string       `json:"path"`
	Lines      int          `json:"lines"`
	IsTest     bool         `json:"is_test"`
	Touched    bool         `json:"touched"`
	Functions  []FuncMetric `json:"functions"`
	Violations []Violation  `json:"violations"`
	Error      string       `json:"error,omitempty"`
}

// Target: satu file plus rentang baris yang berubah. Ranges kosong = seluruh
// file dianggap disentuh (file baru, atau pemanggil tidak punya diff).
type Target struct {
	Path   string   `json:"path"`
	Ranges [][2]int `json:"ranges"`
}

func (t Target) touches(start, end int) bool {
	if len(t.Ranges) == 0 {
		return true
	}
	for _, r := range t.Ranges {
		if r[0] <= end && r[1] >= start {
			return true
		}
	}
	return false
}

func countLines(src []byte) int {
	if len(src) == 0 {
		return 0
	}
	n := bytes.Count(src, []byte("\n"))
	if src[len(src)-1] != '\n' {
		n++
	}
	return n
}

func analyzeFile(t Target, th map[string]int, all bool) FileReport {
	rep := FileReport{Path: t.Path, IsTest: strings.HasSuffix(t.Path, "_test.go"),
		Functions: []FuncMetric{}, Violations: []Violation{}}
	src, err := os.ReadFile(t.Path)
	if err != nil {
		rep.Error = err.Error()
		return rep
	}
	rep.Lines = countLines(src)
	rep.Touched = t.touches(1, rep.Lines)
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, t.Path, src, parser.ParseComments)
	if err != nil {
		rep.Error = err.Error()
		return rep
	}
	for _, decl := range file.Decls {
		fn, ok := decl.(*ast.FuncDecl)
		if !ok || fn.Body == nil {
			continue
		}
		m := measureFunc(fset, fn)
		m.Touched = t.touches(m.Start, m.End)
		rep.Functions = append(rep.Functions, m)
		if m.Touched || all {
			rep.Violations = append(rep.Violations, funcViolations(t.Path, m, th)...)
			if !rep.IsTest {
				rep.Violations = append(rep.Violations, magicViolations(fset, t, fn, m.Name, th, all)...)
			}
		}
	}
	if max, ok := th["file_length"]; ok && rep.Lines > max && (rep.Touched || all) {
		rep.Violations = append(rep.Violations, newViolation(t.Path, 1, "", "file_length", rep.Lines, max,
			"file %d baris > %d"))
	}
	return rep
}

func funcName(fn *ast.FuncDecl) string {
	if fn.Recv == nil || len(fn.Recv.List) == 0 {
		return fn.Name.Name
	}
	typ := fn.Recv.List[0].Type
	if star, ok := typ.(*ast.StarExpr); ok {
		typ = star.X
	}
	if idx, ok := typ.(*ast.IndexExpr); ok { // receiver generik T[K]
		typ = idx.X
	}
	if idx, ok := typ.(*ast.IndexListExpr); ok {
		typ = idx.X
	}
	if id, ok := typ.(*ast.Ident); ok {
		return id.Name + "." + fn.Name.Name
	}
	return fn.Name.Name
}

func measureFunc(fset *token.FileSet, fn *ast.FuncDecl) FuncMetric {
	start := fset.Position(fn.Pos()).Line
	end := fset.Position(fn.End()).Line
	depth := 0
	nestDepth(fn.Body, 0, &depth)
	return FuncMetric{
		Name:       funcName(fn),
		Start:      start,
		End:        end,
		Lines:      end - start + 1,
		Complexity: complexity(fn.Body),
		Nesting:    depth,
		Params:     countParams(fn.Type.Params),
	}
}

func countParams(fl *ast.FieldList) int {
	if fl == nil {
		return 0
	}
	n := 0
	for _, f := range fl.List {
		if len(f.Names) == 0 {
			n++
		} else {
			n += len(f.Names)
		}
	}
	return n
}

func complexity(body ast.Node) int {
	n := 0
	ast.Inspect(body, func(node ast.Node) bool {
		switch x := node.(type) {
		case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt:
			n++
		case *ast.CaseClause:
			if x.List != nil {
				n++
			}
		case *ast.CommClause:
			if x.Comm != nil {
				n++
			}
		case *ast.BinaryExpr:
			if x.Op == token.LAND || x.Op == token.LOR {
				n++
			}
		}
		return true
	})
	return n
}

// nestDepth mencatat kedalaman blok terdalam di bawah n, dengan n sendiri
// berada di level depth.
func nestDepth(n ast.Node, depth int, max *int) {
	ast.Inspect(n, func(c ast.Node) bool {
		if c == n {
			return true
		}
		switch x := c.(type) {
		case *ast.IfStmt:
			walkIf(x, depth, max)
			return false
		case *ast.ForStmt:
			enterBlock(x.Body, depth+1, max)
			return false
		case *ast.RangeStmt:
			enterBlock(x.Body, depth+1, max)
			return false
		case *ast.SwitchStmt:
			enterBlock(x.Body, depth+1, max)
			return false
		case *ast.TypeSwitchStmt:
			enterBlock(x.Body, depth+1, max)
			return false
		case *ast.SelectStmt:
			enterBlock(x.Body, depth+1, max)
			return false
		case *ast.FuncLit:
			enterBlock(x.Body, depth+1, max)
			return false
		}
		return true
	})
}

func enterBlock(b ast.Node, depth int, max *int) {
	if depth > *max {
		*max = depth
	}
	nestDepth(b, depth, max)
}

func walkIf(x *ast.IfStmt, depth int, max *int) {
	if x.Init != nil {
		nestDepth(x.Init, depth, max)
	}
	nestDepth(x.Cond, depth, max)
	enterBlock(x.Body, depth+1, max)
	switch e := x.Else.(type) {
	case *ast.IfStmt:
		walkIf(e, depth, max) // else if: level yang sama, bukan bersarang
	case *ast.BlockStmt:
		enterBlock(e, depth+1, max)
	}
}
