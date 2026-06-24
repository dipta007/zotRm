"""Collection walk: sub-collection mirroring vs. flat mode."""

from conftest import FakeZotero, make_collection, make_item

from zotrm.zotero import iter_items


def _nested_library():
    z = FakeZotero()
    i1 = make_item("I1", "Top paper")
    i2 = make_item("I2", "Sub paper")
    i3 = make_item("I3", "Deep paper")
    z.items = {"C1": [i1], "S1": [i2], "S2": [i3]}
    z.subcollections = {
        "C1": [make_collection("S1", "Sub1")],
        "S1": [make_collection("S2", "Sub2")],
        "S2": [],
    }
    return z


def test_mirror_yields_nested_folders():
    z = _nested_library()
    result = list(iter_items(z, "C1", "/Papers", mirror=True))

    assert [folder for _, folder in result] == [
        "/Papers",
        "/Papers/Sub1",
        "/Papers/Sub1/Sub2",
    ]
    assert [item["key"] for item, _ in result] == ["I1", "I2", "I3"]


def test_flat_mode_stays_in_one_folder():
    z = _nested_library()
    result = list(iter_items(z, "C1", "/Papers", mirror=False))

    assert [folder for _, folder in result] == ["/Papers"]
    assert [item["key"] for item, _ in result] == ["I1"]
