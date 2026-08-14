import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "http://192.168.0.193:3000",
    "192.168.0.193",
  ],
};

export default nextConfig;
