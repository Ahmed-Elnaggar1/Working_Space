# Local free LLM setup for Vault

This project is configured to support a free local model through Ollama without paying for Claude or another hosted provider.

## Recommended option: Ollama

1. Install Ollama from https://ollama.com
2. Pull a model:

```powershell
ollama pull qwen2.5:7b-instruct
```

3. Start the model server:

```powershell
ollama run qwen2.5:7b-instruct
```

4. Keep the project env values as follows:

```env
LLM_PROVIDER=ollama
LLM_API_KEY=placeholder-local-key
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_BASE_URL=http://localhost:11434
```

5. In the backend, the app will call Ollama at:

```text
http://localhost:11434/api/chat
```

## Why this is a good fit

- completely free for local development
- no paid API key required
- works well with the project’s RAG prompt style
- easy to swap later for another provider without changing the app contract

## Good alternative models

- qwen2.5:7b-instruct
- llama3.1:8b-instruct
- mistral:7b-instruct
- phi3.5:mini

## Notes

- This is intended for local development, not production.
- A hosted model can be swapped in later by changing `LLM_PROVIDER` and provider-specific config.
- The app still expects the same answer/citation response contract regardless of provider.
