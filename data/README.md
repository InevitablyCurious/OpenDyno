# data/

What a run keeps outside `runs/`. `runs/` is the record of every cell; nothing here is a second copy of a result.

- `results-ledger.jsonl`: one line per finished cell, with its fingerprint and outcome, kept across runs. A tree
  reset moves it into `runs/backups/<ts>/` beside the tree and starts a new one.
- `tool-jobs.json`: the settings drawer's job history (rebuilds, refreshes), so a job survives a control-plane
  restart.

Both files are ignored by git.
