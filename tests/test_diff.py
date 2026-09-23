from desk.diff import read_diff, split_diff

TWO_FILE_DIFF = """diff --git a/foo.py b/foo.py
index e69de29..4b825dc 100644
--- a/foo.py
+++ b/foo.py
@@ -1 +1,2 @@
-old line
+new line
+another line
diff --git a/bar.py b/bar.py
index e69de29..4b825dc 100644
--- a/bar.py
+++ b/bar.py
@@ -1 +1 @@
-old
+new
"""


def test_split_diff_produces_one_chunk_per_file():
    chunks = split_diff(TWO_FILE_DIFF)

    assert isinstance(chunks, list)
    assert len(chunks) == 2
    assert chunks[0].file == "foo.py"
    assert chunks[1].file == "bar.py"
    assert "new line" in chunks[0].patch
    assert "new" in chunks[1].patch


def test_split_diff_empty_input_returns_message_not_traceback():
    result = split_diff("")

    assert isinstance(result, str)
    assert result.startswith("error:")


def test_split_diff_malformed_input_returns_message_not_traceback():
    result = split_diff("this is not a diff at all, just prose")

    assert isinstance(result, str)
    assert result.startswith("error:")


def test_read_diff_missing_file_returns_message_not_traceback():
    result = read_diff("this/path/does/not/exist.diff")

    assert isinstance(result, str)
    assert result.startswith("error:")


def test_read_diff_reads_existing_file(tmp_path):
    diff_file = tmp_path / "sample.diff"
    diff_file.write_text(TWO_FILE_DIFF, encoding="utf-8")

    result = read_diff(str(diff_file))

    assert result == TWO_FILE_DIFF


def test_read_diff_then_split_diff_end_to_end(tmp_path):
    diff_file = tmp_path / "sample.diff"
    diff_file.write_text(TWO_FILE_DIFF, encoding="utf-8")

    chunks = split_diff(read_diff(str(diff_file)))

    assert isinstance(chunks, list)
    assert len(chunks) == 2
