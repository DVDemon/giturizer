from pathlib import Path

from archdiscovery.analyzer.cpp import analyze_cpp


def test_builds_include_graph_and_classes(tmp_path: Path) -> None:
    (tmp_path / "a.hpp").write_text("class A {};\n", encoding="utf-8")
    (tmp_path / "b.cpp").write_text('#include "a.hpp"\n#include <vector>\n', encoding="utf-8")
    output = tmp_path / "out" / "cpp.json"

    result = analyze_cpp(tmp_path, output)

    assert result["stats"]["files"] == 2
    assert {"from": "b.cpp", "to": "a.hpp", "kind": "include"} in result["dependencies"]
    classes = {name for entry in result["files"] for name in entry["classes"]}
    assert "A" in classes
    assert output.exists()
    assert result["doxygen"]["available"] in {True, False}


def test_parse_doxygen_index_handles_attribute_order() -> None:
    from archdiscovery.analyzer.cpp import _parse_doxygen_index

    xml = (
        '<doxygenindex><compound refid="classA" kind="class"><name>A</name></compound>'
        '<compound refid="ns" kind="namespace"><name>ns</name></compound>'
        '<compound refid="structB" kind="struct"><name>B</name></compound></doxygenindex>'
    )
    assert _parse_doxygen_index(xml) == ["A", "B"]
