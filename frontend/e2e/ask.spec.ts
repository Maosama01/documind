import { expect, test } from "@playwright/test";
import { makePdf } from "./pdf";

// Runs against the whole stack (docker compose up): nginx, the API, the real
// embedding model and Postgres. Nothing is mocked. LLM_PROVIDER is none, so
// the answer comes from the extractive fallback.
const TEXT =
  "Invoices are due within thirty days of receipt. Late payments incur a fee of two percent per month. " +
  "The contract renews every year unless either party cancels it in writing.";

test("sign up, upload a PDF, ask a question and open the cited page", async ({ page }) => {
  const policyViolations: string[] = [];
  page.on("console", (message) => {
    if (message.text().includes("Content Security Policy")) policyViolations.push(message.text());
  });

  await page.goto("/sign-up");
  await page.getByLabel("Full name").fill("End To End");
  await page.getByLabel("Email").fill(`e2e-${Date.now()}@documind-tests.dev`);
  await page.getByLabel("Password").fill("a long test password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Documents" })).toBeVisible();

  await page.getByTestId("file-input").setInputFiles({
    name: "invoice_terms.pdf",
    mimeType: "application/pdf",
    buffer: makePdf(TEXT),
  });
  const row = page.getByRole("row").filter({ hasText: "Invoice Terms" });
  await expect(row.getByText("Ready")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("1 ready to ask")).toBeVisible();

  await row.getByRole("link", { name: "Invoice Terms" }).click();
  await page.getByLabel("Your question").fill("When are invoices due?");
  await page.keyboard.press("Enter");

  await expect(page.getByText("Grounded", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Answered by No LLM: extractive fallback")).toBeVisible();
  await page.getByRole("button", { name: "Show page 1" }).first().click();
  await expect(page.getByRole("heading", { name: "Page 1 of 1" })).toBeVisible();
  await expect(page.getByTitle("PDF, page 1")).toHaveAttribute("src", /^blob:.+#page=1$/);

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect(policyViolations).toEqual([]);
});
