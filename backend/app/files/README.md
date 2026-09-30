# files module

Upload/list/download files; triggers ingestion on upload.

Per TAD section 4 (Backend Module Breakdown). Keep this module's logic isolated —
other modules should only interact with it through its public functions/routes,
never by reaching into its internals directly.
