"""Helper bersama test: import simulate_score dari folder scripts/."""
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.dirname(SCRIPTS_DIR)
RULES_DIR = os.path.join(PLUGIN_DIR, "rules")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import simulate_score  # noqa: E402  (setelah sys.path disiapkan)


def base_block():
    """baseInput() di calculate_test.go: 1 temuan structural + 1 readability di src/a.go."""
    return {
        "findings": [
            {"category": "oversized-function", "evidence": "src/a.go:10"},
            {"category": "naming-convention", "evidence": "src/a.go:99"},
        ],
        "doc_sync_applicable": False,
    }


def set_enabled(cfg, key, enabled):
    for d in cfg["dimensions"]:
        if d["key"] == key:
            d["enabled"] = enabled
