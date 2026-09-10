import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone is for Docker/compose images only. Vercel fails when this is
  // set (missing next-server.js.nft.json during onBuildComplete).
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" as const } : {}),
  allowedDevOrigins: [
    "http://192.168.0.193:3000",
    "192.168.0.193",
  ],
};

export default nextConfig;
