import { test, expect } from "@playwright/test";

test.describe("Session detail polling", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        json: {
          id: 1,
          clerk_user_id: "user_test",
          email: "test@example.com",
          first_name: "Test",
          onboarding_done: true,
          subscription_status: "free",
          learner_profile: null,
          created_at: new Date().toISOString(),
        },
      });
    });
  });

  test("shows processing spinner then coaching text", async ({ page }) => {
    let callCount = 0;

    await page.route("**/api/sessions/42/", async (route) => {
      callCount++;
      const status = callCount >= 2 ? "text_ready" : "processing";
      await route.fulfill({
        json: {
          id: 42,
          session_number: 1,
          status,
          coaching_text:
            status === "text_ready"
              ? {
                  mondaiten: "課題あり",
                  skill: "スキル",
                  next_action: "アクション",
                  success_sign: "サイン",
                }
              : null,
          coaching_video_url: null,
          pipeline_error: null,
          raw_video_url: null,
          voice_memo_url: null,
          self_ratings: {},
          voice_transcript: null,
          structured_input: {},
          video_analysis: {},
          coaching_text_delivered_at: null,
          narration_script: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          user_id: 1,
          dish_id: 1,
        },
      });
    });

    await page.goto("/sessions/42");
    await expect(page.getByText(/AI分析中/)).toBeVisible();

    // After polling transitions to text_ready, coaching text should appear
    await expect(page.getByText("課題あり")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/AI分析中/)).not.toBeVisible();
  });
});
