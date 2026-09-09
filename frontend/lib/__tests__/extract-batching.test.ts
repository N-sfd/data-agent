import { describe, expect, it } from "vitest";

import {
  MAX_TARGET_IDS_PER_REQUEST,
  chunkTargetIds,
} from "@/lib/documents";

describe("Select All extract batching", () => {
  it("keeps the sync batch size at 50", () => {
    expect(MAX_TARGET_IDS_PER_REQUEST).toBe(50);
  });

  it.each([
    [1, [1]],
    [10, [10]],
    [50, [50]],
    [51, [50, 1]],
    [100, [50, 50]],
    [117, [50, 50, 17]],
  ] as const)("chunks %i targets into %j", (count, expectedSizes) => {
    const ids = Array.from({ length: count }, (_, i) => `t${i}`);
    const batches = chunkTargetIds(ids, MAX_TARGET_IDS_PER_REQUEST);
    expect(batches.map((batch) => batch.length)).toEqual([...expectedSizes]);
    expect(batches.flat()).toEqual(ids);
  });
});
