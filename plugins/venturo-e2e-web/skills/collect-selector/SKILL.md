---
name: collect-selector
description: Use this skill to determine the correct data-testid selector for Playwright or end-to-end tests. 
---

# Collect Selector

## Purpose
Determine the correct `data-testid` for a UI component following a strict priority order.

## Logic to collect data-testid
1. if component have attribute/prop `playwrightId` it mean `data-testid` = value of `playwrightId`
2. Else if component have attribute/prop `name` it mean `data-testid` = value of `name`
3. Else if component have attribute/prop `data-testid` it mean `data-testid` = value of `data-testid`
4. Else if component have attribute/prop `label` it mean `data-testid` = value of `label`
5. Else if component have attribute/prop `aria-label` it mean `data-testid` = value of `aria-label`
6. Else If component has text child, use the child text
7. Else use add attribute/prop `playwrightId` with relevan value to that component

**Mandatory** Always pick the highest-priority field that exists and is non-empty (e.g. if any component have `playwrightId="button-add"` it mean `data-testid="button-add`).

## Output Format
Return a simple string containing the resolved `data-testid` value.

If no match is found, return: `"undefined-testid"`
