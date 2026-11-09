---
name: fix_issue
description: Step-by-step method for fixing one reported bug with a minimal, tested patch.
---

# Fix one issue

1. Reproduce: run `python -m pytest -q` and note failing tests.
2. Locate: `grep -rn "<function or word from the issue>" <package>`.
3. Read narrowly: read_file with start_line and end_line around the match.
4. Edit minimally: edit_file with old_string copied exactly from the file.
5. Check: run the tests again.
6. Submit: call submit_patch as soon as the fix is in. Do not edit tests.
