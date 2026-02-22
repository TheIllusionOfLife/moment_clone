import { test, expect } from "@playwright/test";

test.describe("Onboarding flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          json: {
            id: 1,
            clerk_user_id: "user_test",
            email: "test@example.com",
            first_name: "Test",
            onboarding_done: false,
            subscription_status: "free",
            learner_profile: null,
            created_at: new Date().toISOString(),
          },
        });
      } else {
        await route.fulfill({
          json: {
            id: 1,
            clerk_user_id: "user_test",
            email: "test@example.com",
            first_name: "Test",
            onboarding_done: true,
            subscription_status: "free",
            learner_profile: { answers: {} },
            created_at: new Date().toISOString(),
          },
        });
      }
    });
  });

  test("renders 6 onboarding questions", async ({ page }) => {
    await page.goto("/onboarding");
    await expect(page.getByText("あなたについて教えてください")).toBeVisible();
    const radioGroups = page.getByRole("radiogroup");
    await expect(radioGroups).toHaveCount(6);
  });
});
