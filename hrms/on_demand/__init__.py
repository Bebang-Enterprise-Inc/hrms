"""On-demand scripts. Runnable via `bench execute <module>.execute`.

Kept separate from `hrms/patches/` because patches.txt runs exactly ONCE per
environment (once marked DONE in __PatchLog, Frappe never re-runs them).
On-demand scripts are invoked explicitly by an operator when the side effect
is desired — no dry-run trap.
"""
