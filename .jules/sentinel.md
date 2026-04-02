# Sentinel Journal

## 2026-02-21 - [Insufficient File Upload Validation]
**Vulnerability:** The application trusted the `Content-Type` header provided by the client for file uploads (specifically video). A user could upload arbitrary files (e.g., text, executables) masquerading as video files by manipulating the MIME type.
**Learning:** Relying solely on client-provided metadata is insecure. The backend must independently verify the file content.
**Prevention:** Implement file signature (magic bytes) validation. For video files (MP4/MOV), checking for the `ftyp` signature at offset 4 is a robust heuristic. Always validate input at the boundary.
