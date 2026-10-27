# Time to first token: recompute vs. Couchbase KV-cache tier

- Model: `Qwen/Qwen3-8B`
- Prompts: 5 unique prompts of ~10259 tokens

| Prompt | Cold TTFT | TTFT after restart, KV from Couchbase | Cold TTFT after restart (new prompt) | Answer (cold / Couchbase) |
| --- | --- | --- | --- | --- |
| 1 | 2749 ms | 4283 ms | 2690 ms | `The master access code for the ledger is 9714-W.` / `The master access code for the ledger is 9714-W.` |
| 2 | 2791 ms | 3526 ms | 2800 ms | `The master access code for the ledger is 4455-K.` / `The master access code for the ledger is 4455-K.` |
| 3 | 2818 ms | 3968 ms | 2719 ms | `The master access code for the ledger is 4119-K.` / `The master access code for the ledger is 4119-K.` |
| 4 | 2817 ms | 3984 ms | 2680 ms | `The master access code for the ledger is 5314-M.` / `The master access code for the ledger is 5314-M.` |
| 5 | 2766 ms | 3877 ms | 2785 ms | `The master access code for the ledger is 6542-X.` / `The master access code for the ledger is 6542-X.` |

## Summary

```json
{
  "model": "Qwen/Qwen3-8B",
  "prompts": 5,
  "median_prompt_tokens": 10259,
  "median_ttft_ms_cold_before_restart": 2790.5,
  "median_ttft_ms_cold_after_restart": 2718.9,
  "median_ttft_ms_from_couchbase_after_restart": 3968.1,
  "speedup_vs_cold_after_restart": 0.69,
  "chunks_loaded_from_couchbase": 199,
  "all_answers_correct": true,
  "answers_match_cold_run": true,
  "max_first_token_logprob_delta": 0.0071
}
```
