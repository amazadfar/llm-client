# llm-client

**Async LLM + agent runtime kernel for Python.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-pre--release-orange.svg)](#)
[![GitHub stars](https://img.shields.io/github/stars/amirmasoudaz/llm-client?style=social)](https://github.com/amirmasoudaz/llm-client)

`llm-client` sits between your Python application and vendor SDKs. It normalizes OpenAI, Anthropic, and Gemini behind one execution engine with retries, routing, failover, caching, idempotency, and hooks; adds a typed tool and agent runtime; validates structured output with repair; and exposes lifecycle events, redaction, and replay primitives for production debugging. The design choice is framework-level reliability without framework-level opacity. Control flow stays in your application code, not behind a wall of abstractions.

```python
import asyncio

from llm_client.config import load_env
from llm_client.engine import ExecutionEngine, RetryConfig
from llm_client.observability import EngineDiagnosticsRecorder, HookManager
from llm_client.providers import OpenAIProvider
from llm_client.routing import StaticRouter
from llm_client.types import Message, RequestContext, RequestSpec


async def main() -> None:
    load_env()

    primary = OpenAIProvider(model="gpt-5-mini")
    fallback = OpenAIProvider(model="gpt-5-nano")
    diagnostics = EngineDiagnosticsRecorder()

    engine = ExecutionEngine(
        router=StaticRouter([primary, fallback]),
        retry=RetryConfig(attempts=2, backoff=0.25, max_backoff=1.0),
        hooks=HookManager([diagnostics]),
    )

    context = RequestContext(trace_id="readme-demo")
    spec = RequestSpec(
        provider="auto",
        model="gpt-5-mini",
        messages=[Message.user("Summarize the incident in one operational paragraph.")],
        reasoning_effort="minimal",
    )

    try:
        result = await engine.complete(spec, context=context, timeout=30)
        report = diagnostics.latest_request(context.request_id)
        print(result.content)
        print({
            "attempts": report.payload.get("attempts") if report else None,
            "providers_tried": report.payload.get("providers_tried") if report else [],
            "final_status": report.payload.get("final_status") if report else None,
        })
    finally:
        await primary.close()
        await fallback.close()


asyncio.run(main())
```

The quickstart above only needs the base install and `OPENAI_API_KEY`.
Cross-vendor fallback with `AnthropicProvider` requires the `anthropic` extra
and `ANTHROPIC_API_KEY`.

## Features

- **Provider-agnostic kernel.** OpenAI, Anthropic, and Gemini behind one set of messages, content blocks, tool calls, streaming events, and result types.
- **Production execution engine.** Retries, timeouts, routing and failover, circuit breakers, cache, idempotency, and lifecycle hooks wrapped around every call.
- **Typed tool and agent runtime.** Decorator-defined tools, registries, multi-turn loops, streaming, and middleware you can read, replace, or extend.
- **Structured outputs with repair.** JSON schema validation, repair attempts, and full attempt traces. Schema violations surface, they are not silently swallowed.
- **Observability and redaction.** Lifecycle events, a diagnostics recorder, OpenTelemetry and Prometheus hooks, payload previews, and log sanitization.
- **Replay and benchmarks.** Deterministic event recordings, an event bus, and a regression-gate harness for evaluating model behavior over time.

## Install

`llm-client` is not yet on PyPI. Install directly from GitHub:

```bash
pip install "git+https://github.com/amirmasoudaz/llm-client.git"
```

Optional extras for providers, storage, and telemetry:

```bash
pip install "llm-client[anthropic] @ git+https://github.com/amirmasoudaz/llm-client.git"
pip install "llm-client[google] @ git+https://github.com/amirmasoudaz/llm-client.git"
pip install "llm-client[postgres,redis,qdrant] @ git+https://github.com/amirmasoudaz/llm-client.git"
pip install "llm-client[telemetry] @ git+https://github.com/amirmasoudaz/llm-client.git"
pip install "llm-client[all] @ git+https://github.com/amirmasoudaz/llm-client.git"
```

Or clone and install in editable mode:

```bash
git clone https://github.com/amirmasoudaz/llm-client.git
cd llm-client
pip install -e ".[all]"
```

Requires Python 3.10+ and provider credentials such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`. The full dependency matrix is in [docs/llm-client-installation-matrix.md](docs/llm-client-installation-matrix.md).

## Agents and tools

```python
import asyncio

from llm_client.agent import Agent
from llm_client.config import load_env
from llm_client.providers import OpenAIProvider
from llm_client.tools import tool


@tool
async def get_order_status(order_id: str) -> dict:
    """Return the current status for an order."""
    return {
        "order_id": order_id,
        "status": "delayed",
        "reason": "carrier handoff missed the cutoff",
    }


async def main() -> None:
    load_env()
    provider = OpenAIProvider(model="gpt-5-nano")

    try:
        agent = Agent(
            provider=provider,
            tools=[get_order_status],
            system_message="You are a concise support assistant. Use tools before answering.",
            use_middleware=True,
        )

        result = await agent.run("Check order A-104 and draft a customer update.")
        print(result.content)
    finally:
        await provider.close()


asyncio.run(main())
```

The full cookbook lives in [examples/](examples/).

## Documentation

- [Architecture](docs/llm-client-architecture.md)
- [Public API map](docs/llm-client-public-api-v1.md)
- [Package API guide](docs/llm-client-package-api-guide.md)
- [Provider setup](docs/llm-client-provider-setup-guide.md)
- [Guides and cookbook index](docs/llm-client-guides-index.md)
- [Installation matrix](docs/llm-client-installation-matrix.md)
- [Semantic versioning policy](docs/llm-client-semver-policy.md)
- [Support policy](docs/llm-client-support-policy.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
