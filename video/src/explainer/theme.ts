import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const { fontFamily: sans } = loadInter("normal", {
  weights: ["400", "500", "600", "700", "800"],
  subsets: ["latin"],
});
export const { fontFamily: mono } = loadMono("normal", {
  weights: ["400", "600"],
  subsets: ["latin"],
});

export const colors = {
  bg: "#0b0d12",
  panel: "#151a24",
  line: "#2a3142",
  text: "#eef1f7",
  muted: "#97a1b5",
  red: "#ea2328",
  green: "#3ddc84",
  amber: "#ffb547",
  blue: "#5aa9ff",
};

// Numbers measured in the live run recorded in evidence/recordings.
export const run = {
  model: "Qwen3-8B",
  tokens: 10288,
  chunks: 40,
  chunkTokens: 256,
  chunkMB: 36,
  docsPerChunk: 37,
  documents: 1480,
  kvGB: 1.4, // 1,517,027,328 bytes = 1.41 GB in the 1,024-based units used throughout
  ttftComputed: 2.71,
  ttftFromCouchbase: 1.17,
  ttftComputedOnB: 2.65,
  loadSeconds: 0.83,
  answer: "6692-J",
  promptKB: 28, // 27,912 bytes of text
  // Qwen3-8B: per token, a key and a value in each layer, for each KV head.
  layers: 36,
  kvHeads: 8,
  headDim: 128,
  bytesPerNumber: 2, // bfloat16
  kbPerToken: 144, // 2 × 36 × 8 × 128 × 2 bytes = 147,456 bytes
  gpuGB: 24,
  weightsGB: 15.3,
  kvSpaceGB: 2.9, // vLLM: "Available KV cache memory: 2.94 GiB"
};
