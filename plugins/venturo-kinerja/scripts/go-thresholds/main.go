// Command go-thresholds mengukur ambang struktur kinerja (quality-score/
// structural) pada file Go: panjang fungsi, kompleksitas cabang, nesting,
// jumlah parameter, panjang file, dan magic value (heuristik).
//
//	go-thresholds -rules rules/quality-score/structural.md a.go b.go:10-20,40-41
//	echo '{"files":[{"path":"a.go","ranges":[[10,20]]}]}' | go-thresholds -rules ... -stdin
//
// Rentang baris = baris yang berubah di diff; hanya fungsi yang beririsan
// dengannya yang dilaporkan (-all: semua). Output JSON ke stdout. Exit 2 =
// argumen/rules tidak valid; pelanggaran tidak mengubah exit code.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"regexp"
	"strconv"
	"strings"
)

const schemaVersion = 1

type Output struct {
	SchemaVersion int            `json:"schema_version"`
	Rules         string         `json:"rules"`
	Thresholds    map[string]int `json:"thresholds"`
	Files         []FileReport   `json:"files"`
}

var rangeArgRe = regexp.MustCompile(`^(.+\.go):([0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*)$`)

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("go-thresholds", flag.ContinueOnError)
	fs.SetOutput(stderr)
	rules := fs.String("rules", "", "path rules/quality-score/structural.md (wajib)")
	all := fs.Bool("all", false, "laporkan semua fungsi, bukan hanya yang disentuh rentang")
	useStdin := fs.Bool("stdin", false, `baca target dari stdin: {"files":[{"path":..., "ranges":[[a,b]]}]}`)
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *rules == "" {
		fmt.Fprintln(stderr, "go-thresholds: -rules wajib diisi")
		return 2
	}
	th, err := loadThresholds(*rules)
	if err != nil {
		fmt.Fprintln(stderr, "go-thresholds:", err)
		return 2
	}
	targets, err := readTargets(fs.Args(), *useStdin, stdin)
	if err != nil {
		fmt.Fprintln(stderr, "go-thresholds:", err)
		return 2
	}
	out := Output{SchemaVersion: schemaVersion, Rules: *rules, Thresholds: th, Files: []FileReport{}}
	for _, t := range targets {
		out.Files = append(out.Files, analyzeFile(t, th, *all))
	}
	enc := json.NewEncoder(stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(out); err != nil {
		fmt.Fprintln(stderr, "go-thresholds:", err)
		return 2
	}
	return 0
}

func readTargets(args []string, useStdin bool, stdin io.Reader) ([]Target, error) {
	if useStdin {
		var in struct {
			Files []Target `json:"files"`
		}
		if err := json.NewDecoder(stdin).Decode(&in); err != nil {
			return nil, fmt.Errorf("stdin bukan JSON target yang valid: %w", err)
		}
		return in.Files, nil
	}
	targets := make([]Target, 0, len(args))
	for _, a := range args {
		t, err := parseTargetArg(a)
		if err != nil {
			return nil, err
		}
		targets = append(targets, t)
	}
	return targets, nil
}

func parseTargetArg(a string) (Target, error) {
	m := rangeArgRe.FindStringSubmatch(a)
	if m == nil {
		return Target{Path: a}, nil
	}
	t := Target{Path: m[1]}
	for _, part := range strings.Split(m[2], ",") {
		lo, hi, _ := strings.Cut(part, "-")
		start, _ := strconv.Atoi(lo)
		end := start
		if hi != "" {
			end, _ = strconv.Atoi(hi)
		}
		if end < start {
			return Target{}, fmt.Errorf("rentang %q terbalik", part)
		}
		t.Ranges = append(t.Ranges, [2]int{start, end})
	}
	return t, nil
}
