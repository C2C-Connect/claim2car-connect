import assert from "node:assert/strict";
import {
  evaluateGrayGrid,
  QUALITY_GATE_VERSION,
  CaptureQualityError,
  summarizeQualityReport,
} from "../src/modules/capture/quality_gate.mjs";

const textured = Array.from({ length: 24 }, (_, y) =>
  Array.from({ length: 24 }, (_, x) => ((x * 31 + y * 17 + 7) % 200) + 20),
);
const smooth = Array.from({ length: 24 }, (_, y) =>
  Array.from({ length: 24 }, (_, x) => 128 + Math.round((x / 23) * 60)),
);
const dark = Array.from({ length: 16 }, () => Array(16).fill(2));
const flat = Array.from({ length: 16 }, () => Array(16).fill(128));

assert.equal(evaluateGrayGrid(textured).passed, true);
assert.equal(evaluateGrayGrid(smooth).checks.find((check) => check.name === "blur").passed, false);
assert.equal(evaluateGrayGrid(dark).checks.find((check) => check.name === "exposure").passed, false);
assert.equal(evaluateGrayGrid(flat).checks.find((check) => check.name === "flatness").passed, false);
assert.throws(() => evaluateGrayGrid([[1, 2], [3]]), CaptureQualityError);
assert.equal(QUALITY_GATE_VERSION, "quality-gate-v1");
assert.match(summarizeQualityReport(evaluateGrayGrid(dark)), /does not block evidence preservation/);
assert.match(summarizeQualityReport(evaluateGrayGrid(textured)), /passed/);

console.log(JSON.stringify({ suite: "browser-capture-quality-advisory-gate", assertions: 8, status: "passed" }));
