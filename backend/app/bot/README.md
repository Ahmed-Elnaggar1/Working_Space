# bot module

Embeds user questions, queries the vector store scoped to a channel, calls the LLM, returns answers with citations.

Per TAD section 4 (Backend Module Breakdown). Keep this module's logic isolated —
other modules should only interact with it through its public functions/routes,
never by reaching into its internals directly.
