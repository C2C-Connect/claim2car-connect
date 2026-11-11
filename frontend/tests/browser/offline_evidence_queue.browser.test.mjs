// Real Chromium/IndexedDB persistence test. Uses synthetic byte fixtures only.
import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({headless:true});
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("http://127.0.0.1:4173/frontend/tests/browser/offline_evidence_queue.html");
  await page.waitForFunction(() => Boolean(window.c2cQueueHarness));
  await page.evaluate(() => window.c2cQueueHarness.reset());

  // Queue while the browser is offline: original bytes must be committed locally first.
  await context.setOffline(true);
  const queueIds = await page.evaluate(() => window.c2cQueueHarness.seed());
  assert.equal(queueIds.length, 2);
  await context.setOffline(false);

  // A page reload must recover the actual IndexedDB records and their order.
  await page.reload();
  await page.waitForFunction(() => Boolean(window.c2cQueueHarness));
  const restored = await page.evaluate(() => window.c2cQueueHarness.status());
  assert.equal(restored.total, 2);
  assert.equal(restored.pending, 2);
  assert.deepEqual(restored.records.map((record) => record.queueId), queueIds);
  assert.equal("bytes" in restored.records[0], false);

  // A failed first upload must halt FIFO processing without deleting either original.
  const failed = await page.evaluate(() => window.c2cQueueHarness.sync(true));
  assert.equal(failed.result.uploaded, 0);
  assert.equal(failed.result.error, "SYNTHETIC_NETWORK_INTERRUPTION");
  assert.equal(failed.attempted.length, 1);
  assert.equal(failed.attempted[0].queueId, queueIds[0]);
  assert.equal((await page.evaluate(() => window.c2cQueueHarness.status())).pending, 2);

  // Retrying uses the same idempotency identifiers and uploads in the same order.
  const retried = await page.evaluate(() => window.c2cQueueHarness.sync(false));
  assert.equal(retried.result.uploaded, 2);
  assert.deepEqual(retried.attempted.map((item) => item.queueId), queueIds);
  assert.equal(retried.attempted[0].artifactId, failed.attempted[0].artifactId);
  assert.equal(retried.attempted[0].requestId, failed.attempted[0].requestId);

  const uploaded = await page.evaluate(() => window.c2cQueueHarness.status());
  assert.equal(uploaded.uploaded, 2);
  assert.equal(uploaded.pending, 0);
  assert.equal("bytes" in uploaded.records[0], false);

  // Same session in another actor scope is isolated; tenant/session purge clears both.
  await page.evaluate(() => window.c2cQueueHarness.addOtherActor());
  const otherActor = await page.evaluate(() => window.c2cQueueHarness.status("browser-test-other-actor"));
  assert.equal(otherActor.total, 1);
  assert.equal((await page.evaluate(() => window.c2cQueueHarness.status())).total, 2);
  assert.equal(await page.evaluate(() => window.c2cQueueHarness.purge()), 3);
  assert.equal((await page.evaluate(() => window.c2cQueueHarness.status())).total, 0);
  assert.equal((await page.evaluate(() => window.c2cQueueHarness.status("browser-test-other-actor"))).total, 0);
  assert.deepEqual(pageErrors, []);
  await context.close();
  process.stdout.write(JSON.stringify({
    outcome:"passed",
    checks:[
      "offline IndexedDB write",
      "page-reload recovery",
      "FIFO fail-stop",
      "stable retry identifiers",
      "binary removal after acceptance",
      "tenant/actor isolation",
      "tenant/session purge",
    ],
  },null,2)+"\n");
} finally {
  await browser.close();
}
