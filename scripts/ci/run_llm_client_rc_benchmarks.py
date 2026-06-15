from __future__ import annotations

import asyncio
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm_client.agent import ToolExecutionMode
from llm_client.benchmarks import (
    BenchmarkRunMode,
    build_cache_benchmark_case,
    build_completion_benchmark_case,
    build_context_planning_benchmark_case,
    build_embeddings_benchmark_case,
    build_failover_benchmark_case,
    build_stream_benchmark_case,
    build_structured_quality_benchmark_case,
    build_tool_execution_benchmark_case,
    run_benchmarks,
    save_benchmark_report,
)
from llm_client.cache import CacheCore, CachePolicy
from llm_client.cache.base import BaseCacheBackend
from llm_client.context_planning import (
    ContextPlanningRequest,
    DefaultMemoryRetrievalStrategy,
    HeuristicContextPlanner,
)
from llm_client.engine import ExecutionEngine, RetryConfig
from llm_client.hooks import BenchmarkRecorder, HookManager
from llm_client.memory import MemoryWrite, ShortTermMemoryStore
from llm_client.providers.types import (
    CompletionResult,
    EmbeddingResult,
    Message,
    StreamEvent,
    StreamEventType,
    ToolCall,
    Usage,
)
from llm_client.routing import StaticRouter
from llm_client.spec import RequestSpec
from llm_client.structured import StructuredOutputConfig
from llm_client.structured_benchmarks import StructuredBenchmarkCase
from llm_client.tools import Tool, ToolExecutionEngine, ToolRegistry
from tests.llm_client.fakes import ScriptedProvider, ok_result


ARTIFACT_DIR = ROOT / "artifacts" / "benchmarks"
REPORT_PATH = ARTIFACT_DIR / "llm_client_rc_deterministic.json"
COMPARISON_PATH = ARTIFACT_DIR / "llm_client_rc_deterministic_comparison.json"
BASELINE_PATH = ROOT / "tests" / "fixtures" / "benchmarks" / "llm_client_rc_semantic_baseline.v1.json"

_STABLE_METRIC_KEYS: dict[str, set[str]] = {
    "completion_smoke": {"iterations", "success_rate", "avg_total_tokens"},
    "stream_smoke": {"iterations", "success_rate", "avg_stream_token_events"},
    "embeddings_smoke": {"iterations", "avg_embedding_count"},
    "tool_smoke": {"tool_call_count", "success_count", "error_count", "execution_mode"},
    "cache_smoke": {"hit_rate", "cache_hits", "cache_misses", "first_status", "second_status"},
    "failover_smoke": {"status", "ok", "providers_attempted", "fallback_count", "attempt_deltas"},
    "context_smoke": {"selected_entries", "memory_entries", "has_summary", "has_persistent_summary"},
    "structured_smoke": {
        "total_cases",
        "success_rate",
        "repaired_success_rate",
        "repaired_share_of_successes",
        "avg_repair_attempts",
        "max_repair_attempts",
        "repair_attempt_histogram",
    },
}


class _InMemoryCacheBackend(BaseCacheBackend):
    name = "fs"
    default_collection = "rc-bench"

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str | None], dict] = {}

    async def ensure_ready(self) -> None:
        return None

    async def exists(self, effective_key: str, collection: str | None = None) -> bool:
        return (effective_key, collection or self.default_collection) in self._entries

    async def read(self, effective_key: str, collection: str | None = None) -> dict | None:
        return self._entries.get((effective_key, collection or self.default_collection))

    async def write(
        self,
        effective_key: str,
        response: dict,
        model_name: str,
        collection: str | None = None,
    ) -> None:
        _ = model_name
        self._entries[(effective_key, collection or self.default_collection)] = dict(response)


class _DelayedProvider(ScriptedProvider):
    def __init__(
        self,
        *,
        complete_delay: float = 0.002,
        stream_delay: float = 0.002,
        embed_delay: float = 0.002,
        model_name: str = "gpt-5-mini",
    ) -> None:
        super().__init__(model_name=model_name)
        self.complete_delay = complete_delay
        self.stream_delay = stream_delay
        self.embed_delay = embed_delay

    async def complete(self, messages, **kwargs):
        _ = (messages, kwargs)
        self.complete_calls.append({"messages": messages, "kwargs": kwargs})
        await asyncio.sleep(self.complete_delay)
        return ok_result("ok", model=self.model_name)

    async def stream(self, messages, **kwargs):
        _ = (messages, kwargs)
        self.stream_calls.append({"messages": messages, "kwargs": kwargs})
        await asyncio.sleep(self.stream_delay)
        yield StreamEvent(type=StreamEventType.TOKEN, data="hello")
        await asyncio.sleep(self.stream_delay)
        yield StreamEvent(type=StreamEventType.DONE, data=ok_result("hello", model=self.model_name))

    async def embed(self, inputs, **kwargs):
        _ = kwargs
        self.embed_calls.append({"inputs": inputs, "kwargs": kwargs})
        await asyncio.sleep(self.embed_delay)
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        return EmbeddingResult(
            embeddings=[[0.0, 1.0, 0.5] for _ in texts],
            usage=Usage(input_tokens=len(texts), total_tokens=len(texts)),
            model=self.model_name,
            status=200,
        )


@dataclass(frozen=True)
class _Entry:
    role: str
    content: str
    entry_type: str = "message"


def _spec(*, provider: str = "openai") -> RequestSpec:
    return RequestSpec(provider=provider, model="gpt-5-mini", messages=[Message.user("hello")])


def _tool_registry() -> ToolRegistry:
    async def echo_tool(text: str) -> str:
        await asyncio.sleep(0.001)
        return text.upper()

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="Echo text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=echo_tool,
        )
    )
    return registry


def _structured_cases() -> list[StructuredBenchmarkCase]:
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    }
    return [
        StructuredBenchmarkCase(
            name="structured_immediate",
            provider=ScriptedProvider(complete_script=[ok_result('{"value": 1}')]),
            messages=[Message.user("return json")],
            config=StructuredOutputConfig(schema=schema, max_repair_attempts=1),
        ),
        StructuredBenchmarkCase(
            name="structured_repaired",
            provider=ScriptedProvider(
                complete_script=[ok_result('{"value": "oops"}'), ok_result('{"value": 2}')]
            ),
            messages=[Message.user("return json")],
            config=StructuredOutputConfig(schema=schema, max_repair_attempts=1),
        ),
    ]


def _stable_metrics(name: str, metrics: dict[str, Any]) -> dict[str, Any]:
    keys = _STABLE_METRIC_KEYS.get(name, set())
    stable = {key: metrics[key] for key in sorted(keys) if key in metrics}
    return json.loads(json.dumps(stable, sort_keys=True))


def _semantic_snapshot(report: object) -> dict[str, Any]:
    records = []
    for record in sorted(getattr(report, "records", []), key=lambda item: item.name):
        records.append(
            {
                "name": record.name,
                "category": record.category.value,
                "status": record.status,
                "metrics": _stable_metrics(record.name, dict(record.metrics)),
                "labels": dict(record.labels),
                "error": record.error,
            }
        )
    return {
        "schema_version": 1,
        "label": getattr(report, "metadata").label,
        "mode": getattr(report, "metadata").mode.value,
        "total_cases": report.total_cases,
        "success_count": report.success_count,
        "failed_count": report.failed_count,
        "records": records,
    }


def _diff_values(current: Any, baseline: Any, *, path: str = "$") -> list[str]:
    if isinstance(current, dict) and isinstance(baseline, dict):
        diffs: list[str] = []
        current_keys = set(current)
        baseline_keys = set(baseline)
        for key in sorted(current_keys - baseline_keys):
            diffs.append(f"{path}.{key}: unexpected key")
        for key in sorted(baseline_keys - current_keys):
            diffs.append(f"{path}.{key}: missing key")
        for key in sorted(current_keys & baseline_keys):
            diffs.extend(_diff_values(current[key], baseline[key], path=f"{path}.{key}"))
        return diffs
    if isinstance(current, list) and isinstance(baseline, list):
        diffs = []
        if len(current) != len(baseline):
            diffs.append(f"{path}: length {len(current)} != {len(baseline)}")
        for index, (current_item, baseline_item) in enumerate(zip(current, baseline, strict=False)):
            diffs.extend(_diff_values(current_item, baseline_item, path=f"{path}[{index}]"))
        return diffs
    if current != baseline:
        return [f"{path}: {current!r} != {baseline!r}"]
    return []


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


async def _run(*, write_baseline: bool = False) -> int:
    provider = _DelayedProvider()
    cache_engine = ExecutionEngine(
        provider=_DelayedProvider(),
        cache=CacheCore(_InMemoryCacheBackend()),
    )
    first = ScriptedProvider(complete_script=[CompletionResult(status=503, error="unavailable", model="gpt-5-mini")])
    second = _DelayedProvider()
    failover_engine = ExecutionEngine(
        router=StaticRouter([first, second]),
        retry=RetryConfig(attempts=1, backoff=0.0, max_backoff=0.0),
    )

    memory_store = ShortTermMemoryStore()
    await memory_store.write(MemoryWrite(content="funding application status", scope="thread-1"))
    planner = HeuristicContextPlanner(
        memory_reader=memory_store,
        retrieval_strategy=DefaultMemoryRetrievalStrategy(default_scope="thread-1"),
    )
    recorder = BenchmarkRecorder()

    tool_engine = ToolExecutionEngine(_tool_registry())
    cases = [
        build_completion_benchmark_case("completion_smoke", ExecutionEngine(provider=provider), _spec(), iterations=2),
        build_stream_benchmark_case("stream_smoke", ExecutionEngine(provider=_DelayedProvider()), _spec(), iterations=2),
        build_embeddings_benchmark_case(
            "embeddings_smoke",
            ExecutionEngine(provider=_DelayedProvider()),
            ["alpha", "beta"],
            iterations=2,
        ),
        build_tool_execution_benchmark_case(
            "tool_smoke",
            tool_engine,
            [ToolCall(id="1", name="echo", arguments='{"text": "hi"}')],
            mode=ToolExecutionMode.SINGLE,
        ),
        build_cache_benchmark_case(
            "cache_smoke",
            cache_engine,
            _spec(),
            cache_policy=CachePolicy.default_response(collection="bench"),
        ),
        build_failover_benchmark_case(
            "failover_smoke",
            failover_engine,
            _spec(),
            attempt_counters={
                "first": lambda: len(first.complete_calls),
                "second": lambda: len(second.complete_calls),
            },
        ),
        build_context_planning_benchmark_case(
            "context_smoke",
            planner,
            ContextPlanningRequest(
                entries=[_Entry(role="user", content="Need help with my funding application")],
                current_message="funding application",
                max_entries=1,
                summary_scope="thread-1",
            ),
        ),
        build_structured_quality_benchmark_case("structured_smoke", _structured_cases()),
    ]

    report = await run_benchmarks(
        cases,
        label="llm-client-rc-deterministic",
        mode=BenchmarkRunMode.DETERMINISTIC_LOCAL,
        hooks=HookManager([recorder]),
    )
    report_path = save_benchmark_report(report, REPORT_PATH)
    current_snapshot = _semantic_snapshot(report)
    if write_baseline:
        _write_json(BASELINE_PATH, current_snapshot)
        diff_entries: list[str] = []
        status = "baseline_written"
    else:
        baseline_snapshot = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        diff_entries = _diff_values(current_snapshot, baseline_snapshot)
        status = "failed" if diff_entries else "passed"
    _write_json(
        COMPARISON_PATH,
        {
            "status": status,
            "baseline": str(BASELINE_PATH.relative_to(ROOT)),
            "report": str(report_path.relative_to(ROOT)),
            "diffs": diff_entries,
            "current": current_snapshot,
        },
    )

    print("LLM CLIENT RC BENCHMARKS COMPLETED")
    print(f"- report: {report_path}")
    print(f"- baseline: {BASELINE_PATH}")
    print(f"- comparison: {COMPARISON_PATH}")
    print(f"- total_cases: {report.total_cases}")
    print(f"- success_count: {report.success_count}")
    print(f"- recorder_cases: {len(recorder.cases)}")
    print(f"- semantic_status: {status}")
    if diff_entries:
        print("- semantic_diffs:")
        for diff in diff_entries:
            print(f"  - {diff}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic llm-client release-candidate benchmarks.")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="refresh the checked semantic baseline after intentional benchmark behavior changes",
    )
    args = parser.parse_args()
    return asyncio.run(_run(write_baseline=args.write_baseline))


if __name__ == "__main__":
    raise SystemExit(main())
