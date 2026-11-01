
# Assistant module for handling user queries with tool-calling capabilities.    
"""The assistant: a bounded tool-calling loop around the LLM."""
import json
import logging
from dataclasses import dataclass, field

from app import config
from app.llm.client import LLMError, OllamaClient
from app.llm.prompts import get_system_prompt
from app.rag.retriever import Retriever
from app.tools.registry import TOOL_SPECS, Toolbox, parse_text_tool_call

logger = logging.getLogger(__name__)

STEP_LIMIT_ANSWER = "I couldn't complete that request. Please rephrase or give more specific details."
LEAK_ANSWER = ("I can't guarantee any placement; CSSPS decides that. If you share your BECE grades "
               "(English, Mathematics, Science, Social Studies and your electives), I can compute your "
               "aggregate and list schools to consider.")


@dataclass
class AssistantResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


class Assistant:
    def __init__(self, client: OllamaClient | None = None, retriever: Retriever | None = None,
                 prompt_version: str = config.PROMPT_VERSION):
        self.client = client or OllamaClient()
        self.retriever = retriever or Retriever(self.client)
        self.prompt_version = prompt_version

    def ask(self, message: str, history: list[dict] | None = None, grades: dict | None = None) -> AssistantResult:
        toolbox = Toolbox(self.retriever, grades)
        messages = [{"role": "system", "content": get_system_prompt(self.prompt_version)},
                    *(history or []), {"role": "user", "content": message}]
        calls: list[dict] = []

        for step in range(config.MAX_AGENT_STEPS):
            reply = self.client.chat(messages, tools=TOOL_SPECS)
            tool_calls = reply.get("tool_calls") or []
            if not tool_calls:
                recovered = parse_text_tool_call(reply.get("content") or "")
                if recovered:
                    tool_calls = [{"function": recovered}]
            if not tool_calls:
                answer = (reply.get("content") or "").strip()
                if not answer:
                    raise LLMError("The model returned an empty answer.")
                if '"parameters"' in answer or '{"name"' in answer:
                    logger.warning("leaked tool-call text suppressed: %r", answer[:200])
                    answer = LEAK_ANSWER
                return AssistantResult(answer, toolbox.sources, calls)

            # Run one tool per step so later calls can use earlier results (small models batch calls blindly).
            tool_calls = tool_calls[:1]
            messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": tool_calls})
            for call in tool_calls:
                fn = call.get("function", {})
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                result = toolbox.execute(name, args)
                logger.info("step=%d tool=%s args=%s error=%s", step, name, args, result.get("error"))
                calls.append({"tool": name, "arguments": args, "ok": "error" not in result})
                messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})

        logger.warning("agent hit step limit for message=%r", message)
        return AssistantResult(STEP_LIMIT_ANSWER, toolbox.sources, calls)
