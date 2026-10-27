/**
 * KV cache per token and per full-context request, computed from each model's
 * config.json on Hugging Face (bfloat16, 1 KB = 1,024 bytes). Hybrid models
 * also keep a fixed-size state per request that doesn't grow with context.
 * See ../../SOURCES.md for the arithmetic.
 */
export const architectures = [
  { model: "Qwen3-8B", year: "2025 · our demo", kb: 144, label: "144 KB", why: "all 36 layers" },
  { model: "MiniMax-M3", year: "2026", kb: 120, label: "~120 KB", why: "all 60 layers, 4 KV heads" },
  { model: "GLM-5.3", year: "2026", kb: 88, label: "~90 KB", why: "compressed keys and values" },
  { model: "Qwen3.8-27B", year: "2026", kb: 64, label: "64 KB + fixed state", why: "cache in 1 of every 4 layers" },
  { model: "Kimi K3", year: "2026", kb: 27, label: "27 KB + fixed state", why: "compressed, in 24 of 93 layers" },
];

export const fullContext = [
  { model: "Qwen3-8B", context: "40K tokens", gb: 5.6, label: "5.6 GB" },
  { model: "Qwen3.8-27B", context: "262K tokens", gb: 16, label: "16 GB" },
  { model: "Kimi K3", context: "1M tokens", gb: 27, label: "27 GB" },
  { model: "GLM-5.3", context: "1M tokens", gb: 88, label: "~88 GB" },
  { model: "MiniMax-M3", context: "1M tokens", gb: 120, label: "~120 GB" },
];
