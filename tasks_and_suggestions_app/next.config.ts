import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_URL || "https://135.235.219.145.sslip.io"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
