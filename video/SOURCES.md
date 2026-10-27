# Sources quoted in the explainer

Quotes appear verbatim in `src/explainer/sources.ts` and on screen. Each was
checked against the live page on 2026-10-27 (a leading lowercase letter was
capitalized, and one bracketed subject was added, as marked).

| Quote | Source |
|-------|--------|
| “The performance of LLM serving is bottlenecked by memory.” and “[The KV cache] takes up to 1.7GB for a single sequence in LLaMA-13B.” | vLLM team (UC Berkeley), [vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention](https://vllm.ai/blog/2023-06-20-vllm), June 2023. Paper: Kwon et al., [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180), SOSP 2023. |
| “The computational cost of generating this contextual understanding increases quadratically with the length of the input sequence.” | Elmeleegy, Comly, Johnsen, NVIDIA Technical Blog, [5x Faster Time to First Token with NVIDIA TensorRT-LLM KV Cache Early Reuse](https://developer.nvidia.com/blog/5x-faster-time-to-first-token-with-nvidia-tensorrt-llm-kv-cache-early-reuse), Nov 2024. |
| “The total KV cache stored by users has grown rapidly, far exceeding the capacity of GPU memory.” | Liu et al., [LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference](https://arxiv.org/abs/2510.09665), arXiv 2025 (MLSys 2026). |
| “Avoid recalculating a prompt prefix that the model has already processed.” | OpenAI API docs, [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching). |
| “This significantly reduces processing time and costs for repetitive tasks or prompts with consistent elements.” | Anthropic (Claude) docs, [Prompt caching](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching). |

Other useful reading, not quoted: the vLLM paper's finding that existing
systems “waste 60% – 80% of memory due to fragmentation and over-reservation”
(same vLLM blog post), and the Google Gemini API
[context caching](https://ai.google.dev/gemini-api/docs/caching) docs.

## KV-cache figures

Computed from each model's `config.json` on Hugging Face (checked 2026-10-27),
16-bit values, 1 KB = 1,024 bytes. Per token = values kept per token × 2 bytes.

| Model | Config facts | KV cache per token | At full context |
|-------|--------------|--------------------|-----------------|
| [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) (demo) | 36 layers, 8 KV heads, head dim 128 | 2 × 36 × 8 × 128 × 2 B = 144 KB | 40,960 tokens: 5.6 GB |
| [MiniMax-M3](https://huggingface.co/MiniMaxAI/MiniMax-M3) | 60 layers, 4 KV heads, head dim 128 (plus sparse-attention index keys) | 2 × 60 × 4 × 128 × 2 B = 120 KB | 1M tokens: ~120 GB |
| [GLM-5.3](https://huggingface.co/zai-org/GLM-5.3) | 78 MLA layers, kv_lora_rank 512 + rope 64 (plus indexer keys) | 78 × 576 × 2 B ≈ 88 KB | 1M tokens: ~88 GB |
| [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) | 16 of 64 layers full attention (4 KV heads, head dim 256); 48 linear-attention layers keep a fixed ~144 MB state per request | 2 × 16 × 4 × 256 × 2 B = 64 KB | 262,144 tokens: 16 GB |
| [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3) | 24 of 93 layers MLA (512 + 64); the rest linear attention with a fixed state | 24 × 576 × 2 B = 27 KB | 1M tokens: 27 GB |

The demo prompt: 10,288 tokens × 147,456 bytes = 1,517,027,328 bytes = 1.4 GB
(1.5 GB in decimal units, which is what the LMCache logs print: 1509.9 MB for
the 10,240 tokens it stores). Cross-check: the same formula gives Llama-2-13B
(40 layers × 40 heads × 128) 800 KB per token, 1.68 GB for 2,048 tokens,
matching the vLLM team's "up to 1.7GB for a single sequence in LLaMA-13B".
