"""Tests for strip_common_folder_prefix and is_displayable.

strip_common_folder_prefix (issue #10): when a torrent has all files
under the same root folder, the listing should show only the
distinguishing part of the path, not the repeated prefix on every row.

is_displayable (issue #11): only show files that can be played or
viewed — video, music, picture, text. Padding files and other junk
are hidden from the listing.
"""

from lib.utils.kodi.kodi_formats import is_displayable, strip_common_folder_prefix


def _file_stats(paths):
    """Build a minimal file_stats list from path strings."""
    return [{"path": p, "id": str(i)} for i, p in enumerate(paths)]


class TestStripCommonFolderPrefix:
    def test_strips_single_shared_folder(self):
        paths = [
            "Show.Name.720p/Season.1/ep01.mkv",
            "Show.Name.720p/Season.1/ep02.mkv",
        ]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["ep01.mkv", "ep02.mkv"]

    def test_strips_nested_shared_folders(self):
        paths = [
            "Show.Name.720p/Season.1/ep01.mkv",
            "Show.Name.720p/Season.2/ep01.mkv",
        ]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["Season.1/ep01.mkv", "Season.2/ep01.mkv"]

    def test_no_change_when_files_in_root(self):
        paths = ["movie.mkv", "subtitles.srt"]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["movie.mkv", "subtitles.srt"]

    def test_no_change_when_mixed_root_and_folder(self):
        paths = ["file1.mkv", "folder/file2.mkv"]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["file1.mkv", "folder/file2.mkv"]

    def test_no_change_when_different_folders(self):
        paths = ["Movie1/movie.mkv", "Movie2/movie.mkv"]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["Movie1/movie.mkv", "Movie2/movie.mkv"]

    def test_single_file_strips_its_folder(self):
        paths = ["Show.Name.720p/ep01.mkv"]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["ep01.mkv"]

    def test_empty_list_returns_empty(self):
        assert strip_common_folder_prefix([]) == []

    def test_handles_backslash_paths(self):
        paths = [
            "Show.Name.720p\\Season.1\\ep01.mkv",
            "Show.Name.720p\\Season.1\\ep02.mkv",
        ]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == ["ep01.mkv", "ep02.mkv"]

    def test_preserves_distinct_subfolders(self):
        paths = [
            "Show/Season 1/ep01.mkv",
            "Show/Season 1/ep02.mkv",
            "Show/Season 2/ep01.mkv",
            "Show/Extras/interview.mkv",
        ]
        result = strip_common_folder_prefix(_file_stats(paths))
        assert result == [
            "Season 1/ep01.mkv",
            "Season 1/ep02.mkv",
            "Season 2/ep01.mkv",
            "Extras/interview.mkv",
        ]


class TestIsDisplayable:
    def test_video_files_are_displayable(self):
        assert is_displayable("movie.mkv")
        assert is_displayable("Show/Season.1/ep01.mp4")
        assert is_displayable("video.avi")

    def test_music_files_are_displayable(self):
        assert is_displayable("song.mp3")
        assert is_displayable("track.flac")

    def test_picture_files_are_displayable(self):
        assert is_displayable("poster.jpg")
        assert is_displayable("cover.png")

    def test_text_files_are_displayable(self):
        assert is_displayable("readme.txt")
        assert is_displayable("info.nfo")

    def test_pad_files_are_not_displayable(self):
        assert not is_displayable(".pad/79716223")
        assert not is_displayable(".pad/51356901")

    def test_files_without_extension_are_not_displayable(self):
        assert not is_displayable("somefile")
        assert not is_displayable("folder/randomfile")

    def test_non_media_files_are_not_displayable(self):
        assert not is_displayable("setup.exe")
        assert not is_displayable("library.dll")
        assert not is_displayable("data.db")

    def test_pad_with_path_prefix(self):
        assert not is_displayable("Show.Name/.pad/12345")
        assert not is_displayable(".pad/0")
