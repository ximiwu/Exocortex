import { describe, expect, it } from "vitest";

import { buildApiUrl, buildPdfFileUrl, resolveExocortexApiMode } from "./client";

describe("workflow api client helpers", () => {
  it("normalizes api base and path joining", () => {
    expect(buildApiUrl("assets", "/api")).toBe("/api/assets");
    expect(buildApiUrl("/assets", "/api/")).toBe("/api/assets");
    expect(buildApiUrl("/health", "http://localhost:9000/api/")).toBe("http://localhost:9000/api/health");
  });

  it("builds encoded raw pdf file urls", () => {
    expect(buildPdfFileUrl("course/unit 1")).toBe("/api/assets/course%2Funit%201/pdf/file");
  });

  it("resolves api mode deterministically", () => {
    expect(resolveExocortexApiMode(undefined)).toBe("live");
    expect(resolveExocortexApiMode("live")).toBe("live");
    expect(resolveExocortexApiMode("mock")).toBe("mock");
    expect(resolveExocortexApiMode("auto")).toBe("live");
    expect(() => resolveExocortexApiMode("preview")).toThrow('Expected "live" or "mock"');
  });
});
