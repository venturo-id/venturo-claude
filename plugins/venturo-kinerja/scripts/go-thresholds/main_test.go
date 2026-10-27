package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// structural.md asli dari snapshot rules — ambang tidak di-hardcode di test.
var rulesPath = filepath.Join("..", "..", "rules", "quality-score", "structural.md")

func thresholds(t *testing.T) map[string]int {
	t.Helper()
	th, err := loadThresholds(rulesPath)
	if err != nil {
		t.Fatal(err)
	}
	return th
}

func funcByName(t *testing.T, rep FileReport, name string) FuncMetric {
	t.Helper()
	for _, f := range rep.Functions {
		if f.Name == name {
			return f
		}
	}
	t.Fatalf("fungsi %s tidak ditemukan", name)
	return FuncMetric{}
}

func violationKeys(rep FileReport, symbol string) []string {
	var keys []string
	for _, v := range rep.Violations {
		if v.Symbol == symbol {
			keys = append(keys, v.Key)
		}
	}
	return keys
}

func TestLoadThresholdsFromSnapshot(t *testing.T) {
	th := thresholds(t)
	want := map[string]int{"function_length": 50, "function_complexity": 10, "file_length": 800,
		"parameter_count": 5, "nesting_depth": 4, "magic_values": 0}
	for k, v := range want {
		if th[k] != v {
			t.Errorf("%s = %d, mau %d (structural.md v2)", k, th[k], v)
		}
	}
}

func TestLoadThresholdsMissingKeyFails(t *testing.T) {
	path := filepath.Join(t.TempDir(), "structural.md")
	os.WriteFile(path, []byte("- function_length: maks 50\n"), 0o644)
	if _, err := loadThresholds(path); err == nil {
		t.Fatal("rules tanpa function_complexity harus error")
	}
}

func TestMetricsOnFixture(t *testing.T) {
	rep := analyzeFile(Target{Path: "testdata/sample.go"}, thresholds(t), false)
	if rep.Error != "" {
		t.Fatal(rep.Error)
	}
	cases := []struct {
		name                               string
		lines, complexity, nesting, params int
	}{
		{"Short", 6, 1, 1, 1},
		{"Branches", 28, 11, 2, 3},
		{"Deep", 16, 5, 5, 1},
		{"ElseIfChain", 11, 3, 1, 1},
		{"ManyParams", 1, 0, 0, 6},
		{"Repo.FiveParams", 1, 0, 0, 5},
		{"Long", 51, 0, 0, 0},
	}
	for _, c := range cases {
		f := funcByName(t, rep, c.name)
		got := [4]int{f.Lines, f.Complexity, f.Nesting, f.Params}
		want := [4]int{c.lines, c.complexity, c.nesting, c.params}
		if got != want {
			t.Errorf("%s: [lines complexity nesting params] = %v, mau %v", c.name, got, want)
		}
	}
}

func TestViolationsOnFixture(t *testing.T) {
	rep := analyzeFile(Target{Path: "testdata/sample.go"}, thresholds(t), false)
	want := map[string]string{
		"Short":           "",
		"Branches":        "function_complexity,magic_values,magic_values", // `return 3`, `case 3`
		"Deep":            "nesting_depth",
		"ElseIfChain":     "magic_values", // `a == 3`; 0/1/2 dibebaskan
		"ManyParams":      "parameter_count",
		"Repo.FiveParams": "",
		"Long":            "function_length",
		"Magic":           "magic_values,magic_values",
	}
	for sym, keys := range want {
		if got := strings.Join(violationKeys(rep, sym), ","); got != keys {
			t.Errorf("%s: pelanggaran %q, mau %q", sym, got, keys)
		}
	}
	for _, v := range rep.Violations {
		if v.Category == "" {
			t.Errorf("pelanggaran %s tanpa kategori taksonomi", v.Key)
		}
	}
}

func TestOnlyTouchedFunctionsReported(t *testing.T) {
	long := funcByName(t, analyzeFile(Target{Path: "testdata/sample.go"}, thresholds(t), false), "Long")
	rep := analyzeFile(Target{Path: "testdata/sample.go", Ranges: [][2]int{{long.Start + 3, long.Start + 3}}},
		thresholds(t), false)
	if len(rep.Violations) != 1 || rep.Violations[0].Symbol != "Long" {
		t.Fatalf("hanya Long yang disentuh, dapat %+v", rep.Violations)
	}
}

func TestMagicSkippedInTestFiles(t *testing.T) {
	src, _ := os.ReadFile("testdata/sample.go")
	path := filepath.Join(t.TempDir(), "sample_test.go")
	os.WriteFile(path, src, 0o644)
	rep := analyzeFile(Target{Path: path}, thresholds(t), false)
	if keys := violationKeys(rep, "Magic"); len(keys) != 0 {
		t.Fatalf("_test.go tidak boleh punya magic value, dapat %v", keys)
	}
	if keys := violationKeys(rep, "Long"); len(keys) != 1 {
		t.Fatalf("ambang lain tetap dihitung di _test.go, dapat %v", keys)
	}
}

func TestFileLength(t *testing.T) {
	path := filepath.Join(t.TempDir(), "big.go")
	body := "package big\n" + strings.Repeat("\n", 800)
	os.WriteFile(path, []byte(body), 0o644)
	rep := analyzeFile(Target{Path: path}, thresholds(t), false)
	if rep.Lines != 801 || len(rep.Violations) != 1 || rep.Violations[0].Key != "file_length" {
		t.Fatalf("file 801 baris harus melanggar file_length: lines=%d %+v", rep.Lines, rep.Violations)
	}
}

func TestParseErrorReported(t *testing.T) {
	path := filepath.Join(t.TempDir(), "broken.go")
	os.WriteFile(path, []byte("package x\nfunc {"), 0o644)
	if rep := analyzeFile(Target{Path: path}, thresholds(t), false); rep.Error == "" {
		t.Fatal("file rusak harus melaporkan error, bukan diam")
	}
}

func TestCLIArgsAndStdin(t *testing.T) {
	var out, errb bytes.Buffer
	if code := run([]string{"-rules", rulesPath, "testdata/sample.go:20-22"}, nil, &out, &errb); code != 0 {
		t.Fatalf("exit %d: %s", code, errb.String())
	}
	var o Output
	if err := json.Unmarshal(out.Bytes(), &o); err != nil {
		t.Fatal(err)
	}
	if o.SchemaVersion != 1 || len(o.Files) != 1 || o.Files[0].Functions[1].Touched != true {
		t.Fatalf("output tidak sesuai: %+v", o)
	}
	out.Reset()
	stdin := strings.NewReader(`{"files":[{"path":"testdata/sample.go","ranges":[[1,1]]}]}`)
	if code := run([]string{"-rules", rulesPath, "-stdin"}, stdin, &out, &errb); code != 0 {
		t.Fatalf("stdin exit %d", code)
	}
	if code := run([]string{"testdata/sample.go"}, nil, &out, &errb); code != 2 {
		t.Fatalf("tanpa -rules harus exit 2, dapat %d", code)
	}
}
