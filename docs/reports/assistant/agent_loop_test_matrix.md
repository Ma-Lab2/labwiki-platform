# Agent Loop 测试矩阵

- 默认模型：`claude-sonnet-4-5-20250929-thinking`
- 降级模型：`gemini-3.1-pro-preview-all`
- 生成时间：`2026-03-16T18:39:35.393052`

| 用例 | 成功 | 使用模型 | 触发降级 | 结果预览 |
|---|---:|---|---:|---|
| `concept_explain` | `False` | `gemini-3.1-pro-preview-all` | `True` | {"error": "TIMEOUT", "message": "The read operation timed out", "timeout_s": 15} |
| `mechanism_compare_with_context` | `False` | `gemini-3.1-pro-preview-all` | `True` | {"error": "TIMEOUT", "message": "The read operation timed out", "timeout_s": 15} |
| `draft_preview_style` | `False` | `gemini-3.1-pro-preview-all` | `True` | {"error": "TIMEOUT", "message": "The read operation timed out", "timeout_s": 15} |
| `failure_path` | `False` | `gemini-3.1-pro-preview-all` | `True` | {"error": "TIMEOUT", "message": "The read operation timed out", "timeout_s": 15} |
