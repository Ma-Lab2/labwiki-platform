from __future__ import annotations

import json
from typing import Any

import httpx

from ..config import Settings
from .simadvisor_gateway import SimAdvisorGateway


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.backend = settings.llm_backend
        self.openai_enabled = bool(settings.openai_base_url and settings.openai_api_key)
        self.client = httpx.Client(timeout=60.0) if self.openai_enabled else None
        self.simadvisor = None
        if self.backend == "simadvisor":
            self.simadvisor = SimAdvisorGateway(
                settings.simadvisor_executor_path,
                settings.simadvisor_default_model,
                timeout=settings.simadvisor_timeout,
            )

    def answer_from_evidence(
        self,
        *,
        question: str,
        task_type: str,
        detail_level: str,
        mode: str,
        evidence: list[dict[str, Any]],
        unresolved_gaps: list[str],
    ) -> str:
        structured_only = any(
            hint in question for hint in [
                "结构化定义",
                "结构化条目",
                "只给出本组结构化定义",
                "只保留本组结构化定义",
                "只保留结构化定义",
                "只给定义",
            ]
        )
        if self.backend == "simadvisor" and self.simadvisor:
            return self._answer_via_simadvisor(
                question=question,
                task_type=task_type,
                detail_level=detail_level,
                mode=mode,
                evidence=evidence,
                unresolved_gaps=unresolved_gaps,
                structured_only=structured_only,
            )

        if not self.openai_enabled:
            return self._fallback_answer(question, detail_level, evidence, unresolved_gaps)

        system_prompt = (
            "你是实验室私有 MediaWiki 的知识助手。"
            "回答必须以本组语境为先，显式指出证据边界。"
            "如果证据不足，不能把通用答案说成课题组共识。"
        )
        if structured_only:
            system_prompt += " 如果用户要求结构化定义，只能优先使用结构化条目证据，不要复述索引页、模板页或普通导航页。"
        evidence_block = "\n\n".join(
            f"[{index + 1}] {item['title']} ({item['source_type']})\n{item.get('snippet', '')}\n{item.get('content', '')[:800]}"
            for index, item in enumerate(evidence[:6])
        )
        user_prompt = (
            f"问题：{question}\n"
            f"任务类型：{task_type}\n"
            f"解释层级：{detail_level}\n"
            f"模式：{mode}\n"
            f"证据缺口：{'; '.join(unresolved_gaps) if unresolved_gaps else '无'}\n"
            f"结构化优先：{'是' if structured_only else '否'}\n\n"
            f"已检索证据：\n{evidence_block}\n\n"
            "请输出简洁但有层次的中文回答，不要捏造未命中的实验细节。"
        )
        data = self._chat(system_prompt, user_prompt)
        return data["choices"][0]["message"]["content"].strip()

    def draft_from_answer(
        self,
        *,
        question: str,
        answer: str,
        source_titles: list[str],
        draft_prefix: str,
    ) -> dict[str, str]:
        if self.backend == "simadvisor" and self.simadvisor:
            return self._draft_via_simadvisor(
                question=question,
                answer=answer,
                source_titles=source_titles,
                draft_prefix=draft_prefix,
            )

        if not self.openai_enabled:
            title = self._fallback_draft_title(question)
            content = (
                f"== 触发问题 ==\n{question}\n\n"
                f"== 助手整理结果 ==\n{answer}\n\n"
                f"== 来源 ==\n* " + "\n* ".join(source_titles or ["待补充"])
            )
            return {"title": title, "content": content}

        system_prompt = (
            "你负责把知识助手回答整理成 MediaWiki 草稿页。"
            "输出 JSON，字段必须包含 title 和 content。"
        )
        user_prompt = (
            f"草稿前缀：{draft_prefix}\n"
            f"原始问题：{question}\n"
            f"答案：{answer}\n"
            f"来源：{', '.join(source_titles) if source_titles else '待补充'}\n"
            "请输出一个适合课题组私有 wiki 的草稿标题和页面正文。"
        )
        raw = self._chat(system_prompt, user_prompt, response_format={"type": "json_object"})
        payload = json.loads(raw["choices"][0]["message"]["content"])
        return {
            "title": payload.get("title") or self._fallback_draft_title(question),
            "content": payload.get("content") or answer,
        }

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if self.backend == "simadvisor":
            return None
        if not self.openai_enabled or not self.settings.embedding_model or not texts:
            return None
        response = self.client.post(
            f"{self.settings.openai_base_url.rstrip('/')}/embeddings",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.embedding_model,
                "input": texts,
            },
        )
        response.raise_for_status()
        return [item["embedding"] for item in response.json().get("data", [])]

    def _chat(self, system_prompt: str, user_prompt: str, response_format: dict[str, str] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if response_format:
            payload["response_format"] = response_format
        response = self.client.post(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _answer_via_simadvisor(
        self,
        *,
        question: str,
        task_type: str,
        detail_level: str,
        mode: str,
        evidence: list[dict[str, Any]],
        unresolved_gaps: list[str],
        structured_only: bool,
    ) -> str:
        evidence_block = "\n\n".join(
            f"[{index + 1}] {item['title']} ({item['source_type']})\n{item.get('snippet', '')}\n{item.get('content', '')[:800]}"
            for index, item in enumerate(evidence[:6])
        )
        prompt = (
            "你是实验室私有 MediaWiki 的知识助手。\n"
            "回答必须以本组语境为先，显式指出证据边界。\n"
            "如果证据不足，不能把通用答案说成课题组共识。\n\n"
            f"问题：{question}\n"
            f"任务类型：{task_type}\n"
            f"解释层级：{detail_level}\n"
            f"模式：{mode}\n"
            f"证据缺口：{'; '.join(unresolved_gaps) if unresolved_gaps else '无'}\n"
            f"结构化优先：{'是' if structured_only else '否'}\n\n"
            f"已检索证据：\n{evidence_block}\n\n"
            "请输出简洁但有层次的中文回答，不要捏造未命中的实验细节。"
        )
        if structured_only:
            prompt += "\n如果用户要求结构化定义，只能优先使用结构化条目证据，不要复述索引页、模板页或普通导航页。"
        result = self.simadvisor.chat(
            prompt=prompt,
            model=self.settings.simadvisor_default_model,
            temperature=0.2,
            timeout=self.settings.simadvisor_timeout,
        )
        if result.success and result.content:
            return result.content.strip()

        fallback = self.simadvisor.chat(
            prompt=prompt,
            model=self.settings.simadvisor_fallback_model,
            temperature=0.2,
            timeout=self.settings.simadvisor_timeout,
        )
        if fallback.success and fallback.content:
            return fallback.content.strip()

        return self._fallback_answer(question, detail_level, evidence, unresolved_gaps)

    def _draft_via_simadvisor(
        self,
        *,
        question: str,
        answer: str,
        source_titles: list[str],
        draft_prefix: str,
    ) -> dict[str, str]:
        prompt = (
            "请把下面的知识助手回答整理成 MediaWiki 草稿页。\n"
            "输出严格 JSON，对象必须只有 title 和 content 两个字段。\n\n"
            f"草稿前缀：{draft_prefix}\n"
            f"原始问题：{question}\n"
            f"答案：{answer}\n"
            f"来源：{', '.join(source_titles) if source_titles else '待补充'}"
        )
        result = self.simadvisor.chat(
            prompt=prompt,
            model=self.settings.simadvisor_review_model,
            temperature=0.1,
            timeout=self.settings.simadvisor_timeout,
        )
        if result.success and result.content:
            try:
                payload = json.loads(result.content)
                return {
                    "title": payload.get("title") or self._fallback_draft_title(question),
                    "content": payload.get("content") or answer,
                }
            except json.JSONDecodeError:
                pass

        title = self._fallback_draft_title(question)
        content = (
            f"== 触发问题 ==\n{question}\n\n"
            f"== 助手整理结果 ==\n{answer}\n\n"
            f"== 来源 ==\n* " + "\n* ".join(source_titles or ["待补充"])
        )
        return {"title": title, "content": content}

    @staticmethod
    def _fallback_answer(question: str, detail_level: str, evidence: list[dict[str, Any]], unresolved_gaps: list[str]) -> str:
        if not evidence:
            return "当前没有命中足够的站内证据。请先补充关联页面、术语或文献，再让助手继续整理。"
        snippets = []
        for item in evidence[:4]:
            detail = item.get("snippet") or item.get("content", "")[:140]
            snippets.append(f"《{item['title']}》指出：{detail}")
        gap_text = ""
        if unresolved_gaps:
            gap_text = "\n\n仍待补证的部分：\n- " + "\n- ".join(unresolved_gaps)
        return (
            f"针对“{question}”，当前检索到的本组材料更支持以下判断。\n\n"
            + "\n".join(f"{index + 1}. {snippet}" for index, snippet in enumerate(snippets))
            + gap_text
            + f"\n\n解释层级：{detail_level}。如果需要，我可以继续把这些结果整理成草稿预览。"
        )

    @staticmethod
    def _fallback_draft_title(question: str) -> str:
        compact = question.replace("：", " ").replace(":", " ").strip()
        return compact[:42] or "知识助手草稿"
