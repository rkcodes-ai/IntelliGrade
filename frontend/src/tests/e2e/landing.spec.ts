import { expect, test } from "@playwright/test";

test("landing page renders the app title", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "IntelliGrade" })).toBeVisible();
});

test("unknown route renders the 404 page", async ({ page }) => {
  await page.goto("/this-route-does-not-exist");
  await expect(page.getByText("404")).toBeVisible();
});
