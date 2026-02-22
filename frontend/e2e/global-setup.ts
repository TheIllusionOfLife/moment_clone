import { clerk, clerkSetup, setupClerkTestingToken } from "@clerk/testing/playwright";
import { test as setup } from "@playwright/test";
import path from "path";

const authFile = path.join(__dirname, ".auth/user.json");

setup("authenticate", async ({ page }) => {
  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;
  if (!username || !password) {
    throw new Error("E2E_USERNAME and E2E_PASSWORD must be set in your environment for E2E tests.");
  }

  await clerkSetup();

  await setupClerkTestingToken({ page });
  await page.goto("/");

  await clerk.signIn({
    page,
    signInParams: {
      strategy: "password",
      identifier: username,
      password: password,
    },
  });

  await page.context().storageState({ path: authFile });
});
