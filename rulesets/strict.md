# Ruleset: strict

Everything in default.md, plus:

- Flag any function without a type hint on every parameter and return value.
- Flag any catch-all `except:` or `except Exception:` block.
- Flag any mutable default argument.
- Flag any TODO/FIXME left in the diff.
- Treat missing tests for changed (not just new) public functions as a finding, not just new ones.
