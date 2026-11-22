/**
 * Browser-side advisory capture quality gate.
 * It does not reject, mutate, resample, or replace evidence bytes.
 * Thresholds mirror the provisional Python reference gate.
 */
export const QUALITY_GATE_VERSION = "quality-gate-v1";
export const QUALITY_THRESHOLDS = Object.freeze({
  laplacianVarianceMin: 10,
  clippedFractionMax: 0.10,
  uniformFractionMax: 0.60,
  dynamicRangeMin: 16,
});

export class CaptureQualityError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

function validateGrayGrid(pixels) {
  if (
    !Array.isArray(pixels) ||
    !pixels.length ||
    !pixels.every((row) => Array.isArray(row) && row.length) ||
    pixels.some((row) => row.length !== pixels[0].length) ||
    pixels.flat().some((value) => !Number.isInteger(value) || value < 0 || value > 255)
  ) {
    throw new CaptureQualityError("INVALID_PIXELS");
  }
}

export function evaluateGrayGrid(pixels) {
  validateGrayGrid(pixels);
  const height = pixels.length;
  const width = pixels[0].length;
  const flat = pixels.flat();
  const responses = [];

  if (height >= 3 && width >= 3) {
    for (let y = 1; y < height - 1; y += 1) {
      for (let x = 1; x < width - 1; x += 1) {
        responses.push(
          pixels[y][x - 1] + pixels[y][x + 1] +
          pixels[y - 1][x] + pixels[y + 1][x] - 4 * pixels[y][x],
        );
      }
    }
  }

  const mean = responses.length
    ? responses.reduce((sum, value) => sum + value, 0) / responses.length
    : 0;
  const laplacianVariance = responses.length
    ? responses.reduce((sum, value) => sum + (value - mean) ** 2, 0) / responses.length
    : 0;

  let clipped = 0;
  const counts = new Map();
  for (const value of flat) {
    counts.set(value, (counts.get(value) || 0) + 1);
    if (value <= 8 || value >= 247) clipped += 1;
  }

  const clippedFraction = clipped / flat.length;
  const uniformFraction = Math.max(...counts.values()) / flat.length;
  const dynamicRange = Math.max(...flat) - Math.min(...flat);
  const checks = [
    {
      name: "blur",
      passed: laplacianVariance >= QUALITY_THRESHOLDS.laplacianVarianceMin,
      metric: Number(laplacianVariance.toFixed(4)),
      threshold: QUALITY_THRESHOLDS.laplacianVarianceMin,
    },
    {
      name: "exposure",
      passed: clippedFraction <= QUALITY_THRESHOLDS.clippedFractionMax,
      metric: Number(clippedFraction.toFixed(4)),
      threshold: QUALITY_THRESHOLDS.clippedFractionMax,
    },
    {
      name: "occlusion",
      passed: uniformFraction <= QUALITY_THRESHOLDS.uniformFractionMax,
      metric: Number(uniformFraction.toFixed(4)),
      threshold: QUALITY_THRESHOLDS.uniformFractionMax,
    },
    {
      name: "flatness",
      passed: dynamicRange >= QUALITY_THRESHOLDS.dynamicRangeMin,
      metric: dynamicRange,
      threshold: QUALITY_THRESHOLDS.dynamicRangeMin,
    },
  ];

  return Object.freeze({
    version: QUALITY_GATE_VERSION,
    passed: checks.every((check) => check.passed),
    checks: Object.freeze(checks.map(Object.freeze)),
  });
}

/** Decode a photo and analyze a small grayscale canvas. The original is untouched. */
export async function analyzeImageFile(file) {
  if (typeof createImageBitmap !== "function" || typeof document === "undefined") {
    throw new CaptureQualityError("IMAGE_ANALYSIS_UNAVAILABLE");
  }

  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new CaptureQualityError("IMAGE_DECODE_FAILED");
  }

  try {
    const scale = Math.min(1, 256 / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(3, Math.round(bitmap.width * scale));
    const height = Math.max(3, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) throw new CaptureQualityError("CANVAS_UNAVAILABLE");

    context.drawImage(bitmap, 0, 0, width, height);
    const data = context.getImageData(0, 0, width, height).data;
    const pixels = [];

    for (let y = 0; y < height; y += 1) {
      const row = [];
      for (let x = 0; x < width; x += 1) {
        const index = (y * width + x) * 4;
        row.push(Math.round(
          0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2],
        ));
      }
      pixels.push(row);
    }

    return evaluateGrayGrid(pixels);
  } finally {
    bitmap.close?.();
  }
}

export function summarizeQualityReport(report) {
  if (!report) return "Quality analysis unavailable; proceed using operator visual check.";
  const failedChecks = report.checks.filter((check) => !check.passed).map((check) => check.name);
  if (report.passed) {
    return "Local advisory quality gate passed (blur/exposure/occlusion/flatness).";
  }
  return "Local advisory checks flagged " + failedChecks.join(", ") +
    ". Retake is recommended; this advisory does not block evidence preservation.";
}
