import { clerk, clerkSetup, setupClerkTestingToken } from "@clerk/testing/playwright";
import { test as setup } from "@playwright/test";
import path from "path";

const authFile = path.join(__dirname, ".auth/user.json");

setup("authenticate", async ({ page }) => {
  await clerkSetup();

  await setupClerkTestingToken({ page });
  await page.goto("/");

  await clerk.signIn({
    page,
    signInParams: {
      strategy: "password",
      identifier: process.env.E2E_USERNAME!,
      password: process.env.E2E_PASSWORD!,
    },
  });

  await page.context().storageState({ path: authFile });
});
