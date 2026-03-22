from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.llm import LLMClient


class _EnabledProvider:
    enabled = True


class LLMFallbackTests(unittest.TestCase):
    def test_answer_stream_falls_back_on_retryable_generation_error(self) -> None:
        client = object.__new__(LLMClient)
        client.generation_provider = _EnabledProvider()

        with patch.object(LLMClient, "stream_prompt", side_effect=RuntimeError("429 当前模型负载较高")):
            chunks = list(
                LLMClient.answer_stream(
                    client,
                    question="这个机制判断更像哪一类情况？",
                    task_type="compare",
                    detail_level="intro",
                    mode="compare",
                    current_page="Theory:离子加速机制概览",
                    evidence=[{
                        "title": "Theory:离子加速机制概览",
                        "source_type": "wiki",
                        "snippet": "TNSA 与 RPA 判据",
                        "content": "",
                    }],
                    unresolved_gaps=[],
                    conversation_history=[],
                )
            )

        self.assertEqual(len(chunks), 1)
        self.assertIn("当前检索到的本组材料更支持以下判断", chunks[0])


if __name__ == "__main__":
    unittest.main()
