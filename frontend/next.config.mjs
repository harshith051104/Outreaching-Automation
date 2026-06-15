/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    let apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
    if (apiUrl.endsWith("/")) {
      apiUrl = apiUrl.slice(0, -1);
    }
    // If NEXT_PUBLIC_API_URL was set to backend root URL (no /api suffix), add it if not present
    if (!apiUrl.endsWith("/api") && !apiUrl.includes("/api/")) {
      apiUrl = `${apiUrl}/api`;
    }
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
  experimental: {
    proxyTimeout: 300000, // 5 minutes in ms
  },
};

export default nextConfig;
