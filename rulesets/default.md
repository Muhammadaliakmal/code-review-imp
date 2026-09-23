# Ruleset: default

- Flag hardcoded credentials, API keys, or tokens.
- Flag SQL built by string concatenation or f-string interpolation of user input.
- Flag missing input validation on any function that handles external/user data.
- Flag new public functions with no accompanying test.
- Flag inconsistent naming (mixed snake_case/camelCase in the same module).
- Flag functions longer than ~50 lines that could be split.
