from __future__ import annotations

from pathlib import Path


def test_public_api_map_document_exists_and_mentions_core_namespaces() -> None:
    doc = Path("docs/telic-public-api-v1.md")

    assert doc.exists()
    text = doc.read_text()
    assert "## Stable Namespaces" in text
    assert "telic.providers" in text
    assert "telic.types" in text
    assert "telic.content" in text
    assert "telic.observability" in text
    assert "telic.compat" in text
    assert "telic.advanced" in text
    assert "telic.memory" in text


def test_readme_links_to_public_api_map() -> None:
    readme = Path("README.md").read_text()

    assert "docs/telic-public-api-v1.md" in readme


def test_public_readme_links_core_docs() -> None:
    readme = Path("README.md").read_text()
    architecture = Path("docs/telic-architecture.md")
    package_api = Path("docs/telic-package-api-guide.md")
    provider_setup = Path("docs/telic-provider-setup-guide.md")

    assert architecture.exists()
    assert package_api.exists()
    assert provider_setup.exists()
    assert "docs/telic-architecture.md" in readme
    assert "docs/telic-package-api-guide.md" in readme
    assert "docs/telic-provider-setup-guide.md" in readme
