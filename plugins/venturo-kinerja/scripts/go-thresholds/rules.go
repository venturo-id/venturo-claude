package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strconv"
)

// Ambang dibaca dari rules/quality-score/structural.md (snapshot context
// production), baris berbentuk "- function_length: maks 50 — ...". Angka
// tidak di-hardcode di sini: bila context berubah, sync ulang rules/ cukup.
var thresholdLineRe = regexp.MustCompile(`^-\s+([a-z_]+):\s*maks\s+([0-9]+)\b`)

// Kunci ambang yang dihitung program ini beserta kategori taksonomi kinerja
// yang dipakai reviewer untuk pelanggarannya (lihat panduan kategori di
// structural.md). duplication & ui_component_length tidak dihitung untuk Go.
var thresholdCategory = map[string]string{
	"function_length":     "oversized-function",
	"function_complexity": "excessive-complexity",
	"file_length":         "oversized-file",
	"parameter_count":     "too-many-parameters",
	"nesting_depth":       "deep-nesting",
	"magic_values":        "magic-value",
}

// requiredThresholds harus ada di structural.md; tanpa salah satunya hasil
// program ini tidak bisa dipercaya, jadi lebih baik gagal keras.
var requiredThresholds = []string{
	"function_length", "function_complexity", "file_length", "parameter_count", "nesting_depth",
}

func loadThresholds(path string) (map[string]int, error) {
	fh, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer fh.Close()
	found := map[string]int{}
	sc := bufio.NewScanner(fh)
	for sc.Scan() {
		m := thresholdLineRe.FindStringSubmatch(sc.Text())
		if m == nil {
			continue
		}
		n, _ := strconv.Atoi(m[2])
		found[m[1]] = n
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	for _, key := range requiredThresholds {
		if _, ok := found[key]; !ok {
			return nil, fmt.Errorf("%s: ambang %q tidak ditemukan", path, key)
		}
	}
	return found, nil
}
