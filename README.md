# implementation-ai

Two different AI Employee jobs, same kind of system, one repo — per the
project's own instruction to keep "an AI that does real work against
PocketBase" under a single repo rather than splitting by job function.

```
implementation-ai/
  agency_services/          <- NOT YET ADDED to this repo. This is the
                                Implementation Employee that builds/configures
                                purchased Agency services (Voice Agent, Speed
                                to Lead, Lead Reactivation, Custom Agentic AI
                                Employee) for synkra-agency-client-portal
                                clients. Referenced by the project brief as
                                already built (formerly
                                synkra_implementation_employee/) but was not
                                included in what was handed off for this
                                push -- see NOTES.md.
  internal_employees/
    customer_support/        <- Synkra's own internal Customer Support AI
                                Employee. Was ai_worker_customer_support/.
                                Reads/writes synkra-os's PocketBase via its
                                own scoped employee login (see
                                bootstrap_ai_customer_support_employee.sh in
                                synkra-os). Full detail in this package's own
                                README.md.
    # future internal AI Employee roles (sales, admin, etc.) go here as
    # siblings to customer_support/
```

## Why one repo for two different jobs

Both packages are the same *kind* of system even though they do different
work: an AI that reads/writes real PocketBase data, under a human-review
gate for anything risky, tested with mocked PocketBase calls rather than
live ones. Patterns meant to be reused across every package added here:

- **Lazy imports** for anything that isn't needed on every code path.
- **Mocked tests** — no package in this repo talks to a live PocketBase
  instance during its own test suite.
- **DB-driven config over hardcoding** — behavior that might change
  (permission keys, thresholds, service slugs) is read from PocketBase
  records at runtime, not baked into the code.

## Status

- `internal_employees/customer_support/` — present in this push. Its own
  `tests/` directory contains 18 test functions, matching the count the
  original brief expected. I confirmed this by counting `def test_*`
  functions directly, NOT by running the suite — this sandbox has no
  network access to install `httpx`/`pytest`/`pytest-asyncio`, so the
  tests have not actually been executed since the move. Please run
  `pytest` yourself after pushing, before opening the PR, per the
  project's own standard of confirming tests pass before merging.
- `agency_services/` — not present. Needs to be sourced and added before
  this repo matches the brief's target layout.
