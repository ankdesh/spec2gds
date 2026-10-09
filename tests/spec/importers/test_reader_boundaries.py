"""Local importer rules that do not need a document parser or a model."""
from enum import Enum
from types import SimpleNamespace

import pytest

from spec2gds.spec.importers.docling_reader import (
    DoclingDocumentReader,
    ParsedTable,
    _clean_cell,
    _has_ancestor,
    _label_value,
)


@pytest.mark.parametrize("value,expected", [
    (None, ""), (float("nan"), ""), ("  reset\n\t state  ", "reset state"),
    ("  Δ\u00a0signal ", "Δ signal"), (0, "0"), (False, "False"), ("", ""),
])
def test_cell_normalization_keeps_meaning_and_removes_missing_values(value, expected):
    assert _clean_cell(value) == expected


def test_ambiguous_missing_value_does_not_abort_table_import():
    class Ambiguous:
        def __ne__(self, other):
            raise TypeError("Ambiguous missing value")

        def __str__(self):
            return "  valid cell  "
    assert _clean_cell(Ambiguous()) == "valid cell"


@pytest.mark.parametrize("columns,rows,expected", [
    ([], [], None),
    ([None], [[None], [" "]], None),
    (["Signal", "Direction"], [["irq"], ["reset", "in", "extra"]], (("Signal", "Direction", ""), ("irq", "", ""), ("reset", "in", "extra"))),
    ([], [["irq", "out"], [None, " "], ["reset"]], (("irq", "out"), ("reset", ""))),
])
def test_empty_and_irregular_table_rows_have_a_stable_shape(columns, rows, expected):
    dataframe = SimpleNamespace(columns=columns, itertuples=lambda **kwargs: iter(rows))
    table = SimpleNamespace(export_to_dataframe=lambda **kwargs: dataframe)
    result = DoclingDocumentReader().handle_table_item(table, object(), 2)
    assert result == (ParsedTable(expected, 2) if expected else None)


def test_parent_cycles_and_unresolvable_parents_do_not_hang():
    class Table:
        pass
    reference = SimpleNamespace(cref="cycle")
    reference.resolve = lambda document: SimpleNamespace(parent=reference)
    assert not _has_ancestor(SimpleNamespace(parent=reference), None, Table)
    assert not _has_ancestor(SimpleNamespace(parent=object()), None, Table)


def test_label_normalization_accepts_enum_and_qualified_text():
    class Label(Enum):
        SECTION = "section_header"
    assert _label_value(Label.SECTION) == "section_header"
    assert _label_value("DocItemLabel.SECTION_HEADER") == "section_header"


@pytest.mark.parametrize("scale", [0, -1, -0.01])
def test_nonpositive_image_scale_rejected_before_loading_docling(scale):
    with pytest.raises(ValueError, match="greater than zero"):
        DoclingDocumentReader(image_scale=scale)
