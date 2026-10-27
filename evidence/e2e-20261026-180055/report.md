# vLLM + LMCache + Couchbase end-to-end run

- Model: `Qwen/Qwen3-0.6B`
- Started: 2026-10-26T17:00:55.139534+00:00
- Result: **PASS**

| Trial | Prompt tokens | A cold TTFT | B from Couchbase TTFT | B cold TTFT | Chunks from Couchbase | Expected | A answer | B answer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 6775 | 936 ms | 875 ms | 243 ms | 26 | `5606-Y` | `5606-Y` | `5606-Y` |
| 2 | 6787 | 300 ms | 1021 ms | 247 ms | 26 | `4500-H` | `4500-H` | `4500-H` |
| 3 | 6799 | 300 ms | 1104 ms | 251 ms | 26 | `2025-D` | `2025-D` | `2025-D` |

After restarting LMCache server A and vLLM A, the trial-1 prompt was answered `5606-Y` with TTFT 1732 ms, loading 1 chunks from Couchbase.

## Summary

```json
{
  "trials": 3,
  "median_ttft_ms_vllm_a_cold": 300.5,
  "median_ttft_ms_vllm_b_cold": 247.0,
  "median_ttft_ms_vllm_b_from_couchbase": 1020.7,
  "all_answers_correct": true,
  "every_trial_loaded_from_couchbase": true,
  "max_first_token_logprob_delta": 0.0527,
  "couchbase_documents_added": 4524,
  "ttft_ms_vllm_a_after_restart": 1731.9,
  "restart_answer_correct": true,
  "restart_loaded_from_couchbase": true,
  "passed": true
}
```

Couchbase before: `{'item_count': 4524, 'mem_used_mb': 2344.0, 'data_used_mb': 4487.6}`  
Couchbase after: `{'item_count': 9048, 'mem_used_mb': 2199.8, 'data_used_mb': 8910.1}`
