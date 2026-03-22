# SimAdvisor 模型探测报告

- 生成时间：`2026-03-16T18:30:50.902142`
- 探测方式：短 prompt `只回复OK，不要解释。`，超时 45s，`max_tokens=32`

| 模型 | 结果 | 耗时(s) | 预览 |
|---|---:|---:|---|
| `claude-opus-4-6` | `usable` | 3.09 | OK |
| `claude-sonnet-4-5-20250929-thinking` | `usable` | 7.49 | OK |
| `gemini-3.1-pro-preview-all` | `usable` | 7.36 | OK |
| `claude-sonnet-4-20250514-thinking` | `usable` | 35.84 | OK |
| `gemini-3-pro-deepsearch` | `timeout` | 43.44 | {"error": "TIMEOUT", "message": "The read operation timed out", "timeout_s": 45} |
