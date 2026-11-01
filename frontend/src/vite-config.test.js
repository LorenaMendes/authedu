import { describe, expect, it, vi } from "vitest";
import { createViteConfig } from "../vite.config.js";

describe("Vite development server configuration", () => {
  it("keeps the API behind a same-origin proxy", () => {
    const config = createViteConfig({ API_PROXY_TARGET: "http://backend:8000" });

    expect(config.server.host).toBe("127.0.0.1");
    expect(config.server.proxy["/api"].target).toBe("http://backend:8000");
    expect(config.server.proxy["/api"].rewrite("/api/health")).toBe("/health");
    expect(config.server.https).toBeUndefined();
  });

  it("fails closed when HTTPS is requested without both certificate files", () => {
    expect(() =>
      createViteConfig({
        AUTHEDU_DEV_HTTPS: "1",
        AUTHEDU_DEV_TLS_CERT: "/certs/localhost.pem",
        AUTHEDU_DEV_TLS_KEY: "/certs/localhost-key.pem",
      }),
    ).toThrow(/certificate\/key files are unavailable/);
  });

  it("rejects an invalid HTTPS setting instead of silently using HTTP", () => {
    expect(() => createViteConfig({ AUTHEDU_DEV_HTTPS: "true" })).toThrow(
      'AUTHEDU_DEV_HTTPS must be "0" or "1".',
    );
  });

  it("loads configured certificate files when HTTPS is enabled", () => {
    const fileSystem = {
      existsSync: vi.fn().mockReturnValue(true),
      readFileSync: vi.fn((path) => Buffer.from(path)),
    };
    const config = createViteConfig(
      {
        AUTHEDU_DEV_HOST: "0.0.0.0",
        AUTHEDU_DEV_HTTPS: "1",
        AUTHEDU_DEV_TLS_CERT: "/certs/localhost.pem",
        AUTHEDU_DEV_TLS_KEY: "/certs/localhost-key.pem",
      },
      fileSystem,
    );

    expect(config.server.host).toBe("0.0.0.0");
    expect(config.server.https.cert).toEqual(Buffer.from("/certs/localhost.pem"));
    expect(config.server.https.key).toEqual(Buffer.from("/certs/localhost-key.pem"));
  });
});
