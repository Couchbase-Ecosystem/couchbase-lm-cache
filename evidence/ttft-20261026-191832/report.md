# Time to first token: recompute vs. Couchbase KV-cache tier

- Model: `Qwen/Qwen3-8B`
- Prompts: 5 unique prompts of ~10243 tokens

| Prompt | Cold TTFT | TTFT after restart, KV from Couchbase | Cold TTFT after restart (new prompt) | Answer (cold / Couchbase) |
| --- | --- | --- | --- | --- |
| 1 | 2602 ms | 3000 ms | 2665 ms | `The master access code for the ledger is 8216-Z.` / `The master access code for the ledger is 8216-Z.` |
| 2 | 2672 ms | 3500 ms | 2785 ms | `The master access code for the ledger is 1285-S.` / `The master access code for the ledger is 1285-S.` |
| 3 | 2633 ms | 1144 ms | 2752 ms | `The master access code for the ledger is 8790-Q.` / `The master access code for the ledger is 8790-Q.` |
| 4 | 2683 ms | 1088 ms | 2694 ms | `The master access code for the ledger is 3758-H.` / `The master access code for the ledger is 3758-H.` |
| 5 | 2680 ms | 1106 ms | 2691 ms | `The master access code for the ledger is 5376-U.` / `The master access code for the ledger is 5376-U.` |

## Summary

```json
{
  "model": "Qwen/Qwen3-8B",
  "prompts": 5,
  "median_prompt_tokens": 10243,
  "median_ttft_ms_cold_before_restart": 2671.9,
  "median_ttft_ms_cold_after_restart": 2693.7,
  "median_ttft_ms_from_couchbase_after_restart": 1143.9,
  "speedup_vs_cold_after_restart": 2.35,
  "chunks_loaded_from_couchbase": 198,
  "all_answers_correct": true,
  "answers_match_cold_run": true,
  "max_first_token_logprob_delta": 0.0609
}
```
