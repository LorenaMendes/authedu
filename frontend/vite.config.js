import { existsSync, readFileSync } from "node:fs";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export function createViteConfig(environment = process.env, fileSystem = { existsSync, readFileSync }) {
  const httpsSetting = environment.AUTHEDU_DEV_HTTPS;
  if (httpsSetting && httpsSetting !== "0" && httpsSetting !== "1") {
    throw new Error('AUTHEDU_DEV_HTTPS must be "0" or "1".');
  }

  const httpsEnabled = httpsSetting === "1";
  const certificatePath = environment.AUTHEDU_DEV_TLS_CERT;
  const privateKeyPath = environment.AUTHEDU_DEV_TLS_KEY;

  if (
    httpsEnabled &&
    (!certificatePath ||
      !privateKeyPath ||
      !fileSystem.existsSync(certificatePath) ||
      !fileSystem.existsSync(privateKeyPath))
  ) {
    throw new Error(
      "HTTPS is enabled but its certificate/key files are unavailable; follow docs/local-development.md.",
    );
  }

  return {
    plugins: [react()],
    server: {
      host: environment.AUTHEDU_DEV_HOST || "127.0.0.1",
      port: 5173,
      strictPort: true,
      ...(httpsEnabled
        ? {
            https: {
              cert: fileSystem.readFileSync(certificatePath),
              key: fileSystem.readFileSync(privateKeyPath),
            },
          }
        : {}),
      proxy: {
        "/api": {
          target: environment.API_PROXY_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test-setup.js"],
      clearMocks: true,
    },
  };
}

export default defineConfig(createViteConfig());
