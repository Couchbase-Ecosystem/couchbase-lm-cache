/**
 * Quotes shown on screen, copied verbatim from the linked pages (checked
 * 2026-10-27). Keep them verbatim if edited; see ../../SOURCES.md.
 */
export const researchQuotes = [
  {
    quote: "The performance of LLM serving is bottlenecked by memory.",
    extra: "[The KV cache] takes up to 1.7GB for a single sequence in LLaMA-13B.",
    who: "vLLM team, UC Berkeley",
    where: "“vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention”, June 2023",
    url: "vllm.ai/blog/2023-06-20-vllm",
  },
  {
    quote:
      "The computational cost of generating this contextual understanding increases quadratically with the length of the input sequence.",
    who: "NVIDIA Technical Blog",
    where: "“5x Faster Time to First Token with NVIDIA TensorRT-LLM KV Cache Early Reuse”, Nov 2024",
    url: "developer.nvidia.com/blog/5x-faster-time-to-first-token-with-nvidia-tensorrt-llm-kv-cache-early-reuse",
  },
  {
    quote: "The total KV cache stored by users has grown rapidly, far exceeding the capacity of GPU memory.",
    who: "Liu et al., LMCache paper",
    where: "“LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference”, arXiv 2025",
    url: "arxiv.org/abs/2510.09665",
  },
];

export const providerQuotes = [
  {
    quote: "Avoid recalculating a prompt prefix that the model has already processed.",
    who: "OpenAI API docs",
    where: "Prompt caching",
    url: "developers.openai.com/api/docs/guides/prompt-caching",
  },
  {
    quote:
      "This significantly reduces processing time and costs for repetitive tasks or prompts with consistent elements.",
    who: "Anthropic (Claude) docs",
    where: "Prompt caching",
    url: "platform.claude.com/docs/en/docs/build-with-claude/prompt-caching",
  },
];
