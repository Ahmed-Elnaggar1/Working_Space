# ingestion module

Parses uploaded files, chunks them (preserving page numbers), generates embeddings, writes to the vector store.

Per TAD section 4 (Backend Module Breakdown). Keep this module's logic isolated —
other modules should only interact with it through its public functions/routes,
never by reaching into its internals directly.
