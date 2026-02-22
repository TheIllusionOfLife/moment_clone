from typing import BinaryIO


def validate_video_signature(file_obj: BinaryIO) -> bool:
    """Validate video file signature (magic bytes).

    Checks for 'ftyp' at offset 4, which is standard for MP4 and MOV (QuickTime) files.
    This prevents users from uploading arbitrary files disguised as video.
    """
    try:
        # Read the first 12 bytes
        header = file_obj.read(12)
        # Reset file pointer immediately
        file_obj.seek(0)

        # Check for 'ftyp' signature at offset 4
        # ISO base media file format: 4 bytes size + 4 bytes 'ftyp'
        if len(header) >= 8 and header[4:8] == b"ftyp":
            return True

        return False
    except Exception:
        # If reading fails for any reason, assume invalid
        return False
