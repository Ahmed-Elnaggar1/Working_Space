# permissions module

Single source of truth for per-channel role checks. Every other module calls into this — never re-implement a check elsewhere.

Per TAD section 4 (Backend Module Breakdown). Keep this module's logic isolated —
other modules should only interact with it through its public functions/routes,
never by reaching into its internals directly.
