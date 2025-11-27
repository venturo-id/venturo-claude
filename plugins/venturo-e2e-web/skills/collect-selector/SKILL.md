---
name: collect-selector
description: Use this skill to determine the correct data-testid selector for Playwright or end-to-end tests. 
---

# Collect Selector

## Purpose
Determine the correct `data-testid` for a UI component following a strict priority order.

## Priority Rules
Select the first available value from this list:

1. Attribute/prop `playwrightId`
2. Attribute/prop `data-testid`
3. Attribute/prop `name`
4. Attribute/prop `label`
5. Attribute/prop `aria-label`
6. If component has text child, use the child text

Always pick the highest-priority field that exists and is non-empty.

## Output Format
Return a simple string containing the resolved `data-testid` value.

If no match is found, return: `"undefined-testid"`
