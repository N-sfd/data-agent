import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: [
    "http://192.168.0.193:3000",
    "192.168.0.193",
  ],
};

export default nextConfig;
