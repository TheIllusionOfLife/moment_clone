import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSessionUpload } from "@/hooks/use-session-upload";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock api
const mockApiFetch = vi.fn();
const mockApiUpload = vi.fn();

vi.mock("@/lib/api", () => ({
  useApi: () => ({
    apiFetch: mockApiFetch,
    apiUpload: mockApiUpload,
  }),
}));

describe("useSessionUpload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const defaultProps = {
    slug: "fried-rice",
    videoFile: new File([""], "video.mp4", { type: "video/mp4" }),
    customDishName: "",
    memoText: "Test memo",
    ratings: { appearance: 3, taste: 3, texture: 3, aroma: 3 },
  };

  it("should handle successful upload", async () => {
    const sessionId = 123;
    mockApiFetch
      .mockResolvedValueOnce({ id: sessionId }) // create session
      .mockResolvedValueOnce({}) // memo
      .mockResolvedValueOnce({}); // ratings
    mockApiUpload.mockResolvedValueOnce({}); // upload

    const { result } = renderHook(() => useSessionUpload(defaultProps.slug));

    expect(result.current.uploading).toBe(false);
    expect(result.current.error).toBe(null);

    await act(async () => {
      await result.current.handleUpload(
        defaultProps.videoFile,
        defaultProps.customDishName,
        defaultProps.memoText,
        defaultProps.ratings
      );
    });

    expect(mockApiFetch).toHaveBeenCalledTimes(3);
    // 1. Create session
    expect(mockApiFetch).toHaveBeenNthCalledWith(1, "/api/sessions/", {
      method: "POST",
      body: JSON.stringify({ dish_slug: defaultProps.slug }),
    });
    // 2. Upload video (apiUpload)
    expect(mockApiUpload).toHaveBeenCalledTimes(1);
    expect(mockApiUpload).toHaveBeenCalledWith(
        `/api/sessions/${sessionId}/upload/`,
        expect.any(FormData)
    );
    // 3. Memo
    expect(mockApiFetch).toHaveBeenNthCalledWith(2, `/api/sessions/${sessionId}/memo-text/`, {
        method: "POST",
        body: JSON.stringify({ text: defaultProps.memoText }),
    });
    // 4. Ratings
    expect(mockApiFetch).toHaveBeenNthCalledWith(3, `/api/sessions/${sessionId}/ratings/`, {
        method: "PATCH",
        body: JSON.stringify(defaultProps.ratings),
    });

    expect(mockPush).toHaveBeenCalledWith(`/sessions/${sessionId}`);
    expect(result.current.uploading).toBe(true);
  });

  it("should validation error for free slug without custom name", async () => {
    const { result } = renderHook(() => useSessionUpload("free"));

    await act(async () => {
        await result.current.handleUpload(
            defaultProps.videoFile,
            "", // empty custom name
            defaultProps.memoText,
            defaultProps.ratings
        );
    });

    expect(result.current.error).toBe("料理名を入力してください");
    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it("should handle api error during session creation", async () => {
    mockApiFetch.mockRejectedValue(new Error("API Error"));

    const { result } = renderHook(() => useSessionUpload(defaultProps.slug));

    await act(async () => {
        await result.current.handleUpload(
            defaultProps.videoFile,
            defaultProps.customDishName,
            defaultProps.memoText,
            defaultProps.ratings
        );
    });

    expect(result.current.error).toBe("API Error");
    expect(result.current.uploading).toBe(false);
  });
});
