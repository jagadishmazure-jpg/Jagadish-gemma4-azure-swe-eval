# Security policy

This is a portfolio project. Nothing in it is deployed, and it holds no real data: the company
(Tallowmere Freight) is fictional, its code base was written for this repository, and every issue
and test is synthetic.

## Report a vulnerability

Please report privately to the repository owner through GitHub (the **Security** tab, **Report a
vulnerability**, when available). Please do not open a public issue. First reply within a week.

## Controls in place

- Model-written shell commands run inside bubblewrap: system directories and the Python environment
  are mounted read-only, the task workspace is the only writable place, there is no network and no
  home directory. Without bubblewrap, only an allowlist of read and test commands runs, with no shell.
- File tools resolve every path inside the task workspace and refuse anything outside it.
- Tool-call, turn, output-size and time budgets on every task.
- The agent only produces a patch. Nothing it writes is merged or deployed; the patch is re-checked
  on a fresh checkout with tests it never saw.
- Model output is scrubbed of real brand names before it is stored or scored.
- Secret scanning with push protection, Dependabot alerts and security updates
- CodeQL (`security-and-quality`) on every push and weekly when code scanning is available (it needs
  GitHub Code Security while the repository is private; the job is skipped until then)
- gitleaks over the full git history in CI
- Every GitHub Action pinned to a commit SHA; workflow tokens are read-only
- Branch rules for `main` (no force-push or deletion, required CI checks) are not enforced while the repository is private on the current plan; they are applied once it is public or the plan allows it
- The deploy workflow is manual, gated by `DEPLOY_ENABLED`, and logs in with OIDC (no client secret)
- Model weights come from pinned revisions and are checked by SHA-256; GGUF only, never pickle files
- Measured trajectories are checked against a hash manifest, so a changed data file fails CI
