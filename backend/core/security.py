import filetype


def validate_video_magic(file_header: bytes) -> bool:
    """
    Validates the magic bytes of the file header to ensure it's a video.

    Args:
        file_header: The first few bytes of the file (at least 2048 bytes recommended).

    Returns:
        True if the file signature matches allowed video types (mp4, mov).
    """
    kind = filetype.guess(file_header)
    if kind is None:
        return False

    # filetype returns 'video/mp4' for MP4
    # filetype returns 'video/quicktime' for MOV
    return kind.mime in {"video/mp4", "video/quicktime"}
