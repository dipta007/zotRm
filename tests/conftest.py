"""Shared test doubles: a fake pyzotero client and a fake rmapi subprocess."""

import subprocess

import pytest


class FakeZotero:
    """In-memory stand-in for ``pyzotero.Zotero`` covering the API we use."""

    def __init__(self):
        self.collections_list = []
        self.items = {}  # collection key -> list[item]
        self.subcollections = {}  # collection key -> list[collection]
        self.children_map = {}  # item key -> list[attachment]
        self.files = {}  # attachment key -> bytes
        self.added_tags = []  # (item key, tag)
        self.attachments = []  # (paths, parent key)
        self.deleted = []  # deleted item dicts
        self.created = []  # created item templates
        self.item_count = 0  # value returned by num_items()

    def everything(self, result):
        return result

    def num_items(self):
        return self.item_count

    def delete_item(self, item):
        self.deleted.append(item)

    def item_template(self, item_type, link_mode=None):
        return {}

    def create_items(self, items):
        self.created.extend(items)
        return {"success": {"0": "NEWKEY"}}

    def collections(self):
        return self.collections_list

    def collection_items_top(self, key):
        return self.items.get(key, [])

    def collections_sub(self, key):
        return self.subcollections.get(key, [])

    def children(self, item_key):
        return self.children_map.get(item_key, [])

    def file(self, att_key):
        return self.files.get(att_key, b"%PDF-1.4 fake")

    def add_tags(self, item, *tags):
        for tag in tags:
            self.added_tags.append((item["key"], tag))

    def attachment_simple(self, paths, parent_key):
        self.attachments.append((list(paths), parent_key))
        return {"successful": {}}


def make_item(key, title, tags=()):
    return {"key": key, "data": {"title": title, "tags": [{"tag": t} for t in tags]}}


def make_collection(key, name):
    return {"key": key, "data": {"name": name}}


def make_pdf_child(key, filename):
    return {"key": key, "data": {"contentType": "application/pdf", "filename": filename}}


class _Answer:
    def __init__(self, value):
        self.value = value

    def ask(self):
        return self.value


class FakeQuestionary:
    """Returns canned answers in the order the prompts are shown."""

    def __init__(self, answers):
        self._answers = list(answers)
        self._i = 0

    def _next(self):
        value = self._answers[self._i]
        self._i += 1
        return _Answer(value)

    def text(self, *a, **k):
        return self._next()

    def password(self, *a, **k):
        return self._next()

    def select(self, *a, **k):
        return self._next()

    def confirm(self, *a, **k):
        return self._next()

    def path(self, *a, **k):
        return self._next()


class RmapiRecorder:
    """Records every rmapi invocation and returns a successful result."""

    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


@pytest.fixture
def fake_zot():
    return FakeZotero()


@pytest.fixture
def rmapi_run(monkeypatch):
    """Patch the rmapi subprocess and reset the per-process folder cache."""
    import zotrm.remarkable as remarkable

    remarkable._MADE_FOLDERS.clear()
    recorder = RmapiRecorder()
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", recorder)
    return recorder
