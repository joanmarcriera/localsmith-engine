# Local Ollama and SearXNG Routing

This workflow should prefer local LAN tools before spending cloud subscription or API quota.

## Endpoints

- Ollama: `http://192.168.0.5:30068`
- SearXNG: `http://192.168.0.5:30053`

Configure them in `.env`:

```bash
export OLLAMA_HOST=http://192.168.0.5:30068
export SEARXNG_HOST=http://192.168.0.5:30053
```

## Intended routing

| Workflow need | Default local route | Notes |
|---|---|---|
| Fresh web facts before planning | `bin/search` via SearXNG | Use this before asking a cloud model for current docs or examples. |
| Scaffold JSON trees | `OLLAMA_SCAFFOLD_MODEL=qwen2.5-coder:7b` | Lower VRAM pressure and fast enough for structured file lists. |
| Local code review | `OLLAMA_REVIEW_MODEL=qwen2.5-coder:14b` | Slower, but better than small models for code review. |
| Cheap classification / triage | `qwen3:4b` or `phi3:mini` | Good for routing decisions and short summaries. |
| Reasoning experiments | `deepseek-r1:8b` | Use only when verbose reasoning is acceptable. |
| Embeddings | `nomic-embed-text:latest` or `mxbai-embed-large:latest` | These are not chat models; use Ollama embedding endpoints. |
| Reranking | `jina-reranker-v3-BF16:latest` | Keep separate from normal generation. |
| Vision | `llava:7b` | Only useful if image inputs are added later. |

`bin/ai` supports `--model` for one-off overrides:

```bash
bin/ai ollama "Review this function" --model qwen2.5-coder:7b
```

When the workflow scripts run, they set `AIWF_PROJECT` and `AIWF_STEP`. `bin/ai`
uses those values to choose role-specific model env vars and to write per-project
usage into `logs/tokens.jsonl`.

## Available Ollama models

Inventory supplied from the LAN host:

| Model | Parameters | Quantization | Size | Suggested use |
|---|---:|---|---:|---|
| `glm-4.7-flash:latest` | 29.9B | Q4_K_M | 19.0 GB | Experimental only on 8 GB VRAM; expect offload. |
| `codellama:7b` | 7B | Q4_0 | 3.8 GB | Legacy code fallback. |
| `nomic-embed-text:latest` | 137M | F16 | 274 MB | Embeddings. |
| `phi3:mini` | 3.8B | Q4_0 | 2.2 GB | Cheap local triage. |
| `qwen2.5-coder:14b` | 14.8B | Q4_K_M | 9.0 GB | Local review default; may offload. |
| `qwen2.5-coder:7b` | 7.6B | Q4_K_M | 4.7 GB | Scaffold and fast code tasks. |
| `llava:7b` | 7B | Q4_0 | 4.7 GB | Vision. |
| `mxbai-embed-large:latest` | 334M | F16 | 670 MB | Embeddings. |
| `qwen2.5:7b` | 7.6B | Q4_K_M | 4.7 GB | General local fallback. |
| `mistral-small:24b` | 23.6B | Q4_K_M | 14.3 GB | Experimental only; likely offload. |
| `deepseek-r1:8b` | 8.2B | Q4_K_M | 5.2 GB | Reasoning experiments. |
| `nemotron-3-nano:30b` | 31.6B | Q4_K_M | 24.3 GB | Experimental only; likely offload. |
| `llama3.2:3b` | 3.2B | Q4_K_M | 2.0 GB | Very small local fallback. |
| `jina-reranker-v3-BF16:latest` | 596M | BF16 | 1.2 GB | Reranking. |
| `qwen2.5:7b-instruct` | 7.6B | Q4_K_M | 4.7 GB | General local instruction tasks. |
| `qwen3:4b` | 4.0B | Q4_K_M | 2.5 GB | Cheap local triage. |
| `llama3.1:8b` | 8.0B | Q4_K_M | 4.9 GB | General fallback. |
| `ministral-3:14b` | 13.9B | Q4_K_M | 9.1 GB | Experimental code/general tasks; may offload. |
| `llama3:latest` | 8.0B | Q4_0 | 4.7 GB | General fallback. |

On an RTX 4060 with 8 GB VRAM, prefer the 3B-8B models for unattended high-volume
steps. Larger models may run with CPU offload, but measure wall time before making
them defaults.
