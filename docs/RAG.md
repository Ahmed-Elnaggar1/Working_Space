# RAG (Retrieval-Augmented Generation) Workflow Architecture

## 1. Ingestion Pipeline (Document Processing)
**File Coordinator**: `backend/app/ingestion/pipeline.py`
**Trigger**: File upload to a channel.

1. **Storage Retrieval**: Downloads the uploaded file bytes from storage (`backend/app/files/storage.py`).
2. **Parsing** (`backend/app/ingestion/parser.py`):
   - Extracts text page-by-page.
   - Supports `.pdf` (via `pypdf`) and `.txt`.
   - Output: List of `(page_number, page_text)` tuples.
3. **Chunking** (`backend/app/ingestion/chunker.py`):
   - **Heading Detection**: Identifies Markdown headings, explicit "Section/Chapter" headers, and short all-caps lines to track the current section.
   - **Word-Level Splitting**: Splits text into chunks of `max_words` (default: 350).
   - **Overlap**: Retains a rolling overlap of `overlap` words (default: 50) between consecutive chunks of the same page.
   - Output: List of dictionaries containing `page_number`, `section`, and `content`.
4. **Embedding Generation** (`backend/app/ingestion/embeddings.py`):
   - Applies deterministic SHA-256 hashing on text to produce L2-normalized float vectors.
5. **Database Storage** (`backend/app/models.py`):
   - Saves chunks (with `file_id`, `channel_id`, `page_number`, `section`, `content`, and `embedding`) to the `Chunk` table.

---

## 2. Frontend Request Initiation
**Core File**: `frontend/src/features/channels/bot.ts`
**UI Components**: `frontend/src/features/channels/components/BotAskPanel.tsx`

1. **Validation**: Validates user question (e.g., max 4000 characters).
2. **API Call**: Sends a `POST` request with the question to `/channels/{channel_id}/ask`.
3. **Response Handling**: Processes the bot's response, manages errors, handles timeouts, and structures `BotCitation` data.

---

## 3. Backend Retrieval & Generation (RAG)
**Route Handler**: `backend/app/bot/routes.py`
**LLM Logic**: `backend/app/bot/llm.py`

1. **Similarity Search**: 
   - `routes.py` invokes `search_channel_chunks` to search the database.
   - Filters by `channel_id` for authorization/scoping.
   - Applies `INSUFFICIENT_EVIDENCE_THRESHOLD` to filter out low-relevance chunks.
2. **Context Building**:
   - Maps retrieved chunks to structured context: `file_name`, `page_number`, and `content`.
3. **Prompt Construction** (`llm.py`):
   - Uses `RAG_PROMPT_TEMPLATE`.
   - Enforces strict grounded answering based *only* on the provided context.
   - Demands explicit citations (file name and page number) for facts.
4. **LLM Execution** (`llm.py`):
   - Instantiates the correct client (`ClaudeClient`, `OllamaClient`, or `PlaceholderLLMClient`) based on configuration.
   - Calls the model and parses the response.
5. **Citation Formatting**:
   - Maps the utilized chunks into a deduplicated list of citations (`file_id`, `file_name`, `page`).
6. **Response Delivery**:
   - Returns the `answer`, `citations`, and a boolean `insufficient_evidence` flag to the frontend.
