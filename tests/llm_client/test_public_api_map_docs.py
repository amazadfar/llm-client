from __future__ import annotations

from pathlib import Path


def test_public_api_map_document_exists_and_mentions_core_namespaces() -> None:
    doc = Path("docs/llm-client-public-api-v1.md")

    assert doc.exists()
    text = doc.read_text()
    assert "## Stable Namespaces" in text
    assert "llm_client.providers" in text
    assert "llm_client.types" in text
    assert "llm_client.content" in text
    assert "llm_client.observability" in text
    assert "llm_client.compat" in text
    assert "llm_client.advanced" in text
    assert "llm_client.memory" in text


def test_readme_links_to_public_api_map() -> None:
    readme = Path("README.md").read_text()

    assert "docs/llm-client-public-api-v1.md" in readme


def test_public_readme_links_core_docs() -> None:
    readme = Path("README.md").read_text()
    architecture = Path("docs/llm-client-architecture.md")
    package_api = Path("docs/llm-client-package-api-guide.md")
    provider_setup = Path("docs/llm-client-provider-setup-guide.md")

    assert architecture.exists()
    assert package_api.exists()
    assert provider_setup.exists()
    assert "docs/llm-client-architecture.md" in readme
    assert "docs/llm-client-package-api-guide.md" in readme
    assert "docs/llm-client-provider-setup-guide.md" in readme
