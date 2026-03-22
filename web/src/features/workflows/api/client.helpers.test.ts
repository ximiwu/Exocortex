import { describe, expect, it } from "vitest";

import { buildApiUrl, buildPdfPageImageUrl, resolveExocortexApiMode } from "./client";

describe("workflow api client helpers", () => {
  it("normalizes api base and path joining", () => {
    expect(buildApiUrl("assets", "/api")).toBe("/api/assets");
    expect(buildApiUrl("/assets", "/api/")).toBe("/api/assets");
    expect(buildApiUrl("/health", "http://localhost:9000/api/")).toBe("http://localhost:9000/api/health");
  });

  it("builds encoded pdf image url with normalized dpi", () => {
    expect(buildPdfPageImageUrl("course/unit 1", 3, 180.6)).toBe(
      "/api/assets/course%2Funit%201/pdf/pages/3/image?dpi=181",
    );
    expect(buildPdfPageImageUrl("asset-a", 0, 0)).toBe("/api/assets/asset-a/pdf/pages/0/image?dpi=1");
  });

  it("resolves api mode deterministically", () => {
    expect(resolveExocortexApiMode(undefined)).toBe("live");
    expect(resolveExocortexApiMode("live")).toBe("live");
    expect(resolveExocortexApiMode("mock")).toBe("mock");
    expect(resolveExocortexApiMode("auto")).toBe("live");
    expect(() => resolveExocortexApiMode("preview")).toThrow('Expected "live" or "mock"');
  });
});
