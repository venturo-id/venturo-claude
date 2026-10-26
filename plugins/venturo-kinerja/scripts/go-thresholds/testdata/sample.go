package sample

import (
	"errors"
	"fmt"
)

type Repo struct{}

// Short is well within every threshold.
func Short(a int) int {
	if a > 0 {
		return a
	}
	return 0
}

// Branches has exactly 11 branch points: 3 if/else-if, 1 for, 3 case, 2 &&/||, 1 range, 1 if.
func Branches(a, b int, xs []int) int {
	if a > 0 && b > 0 {
		return 1
	} else if a < 0 || b < 0 {
		return 2
	} else if a == b {
		return 3
	}
	for i := 0; i < a; i++ {
		b++
	}
	switch a {
	case 1:
		b++
	case 2:
		b--
	case 3:
		b *= 2
	default:
		b = 0
	}
	for _, x := range xs {
		if x == b {
			return x
		}
	}
	return b
}

// Deep nests five levels below the body.
func Deep(xs [][]int) int {
	total := 0
	for _, row := range xs {
		for _, v := range row {
			if v > 0 {
				switch v {
				case 2:
					if total > 0 {
						total += v
					}
				}
			}
		}
	}
	return total
}

// ElseIfChain stays at nesting 1 however long the chain gets.
func ElseIfChain(a int) string {
	if a == 1 {
		return "one"
	} else if a == 2 {
		return "two"
	} else if a == 3 {
		return "three"
	} else {
		return "many"
	}
}

func ManyParams(a, b, c int, d string, e, f bool) {}

func (r *Repo) FiveParams(a, b, c, d, e int) {}

func Magic(n int) error {
	const limit = 100
	timeout := 42
	if n > limit+timeout {
		return fmt.Errorf("melebihi %d", 500)
	}
	if n == 7 {
		return errors.New("tujuh")
	}
	return nil
}

func Long() int {
	x := 0
	// baris 3

	x++
	x++
	x++
	x++
	x++
	x++

	x++
	x++
	x++
	x++
	x++
	x++

	x++
	x++
	x++
	x++
	x++
	x++

	x++
	x++
	x++
	x++
	x++
	x++

	x++
	x++
	x++
	x++
	x++
	x++

	x++
	x++
	x++
	x++
	x++
	x++
	// komentar tetap dihitung

	x++
	x++
	return x
}
