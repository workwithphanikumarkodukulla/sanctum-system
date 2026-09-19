import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["192.168.1.6", "localhost:3000", "127.0.0.1:3000"],
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: "http://127.0.0.1:5050/api/:path*",
      },
    ];
  },
};

export default nextConfig;
