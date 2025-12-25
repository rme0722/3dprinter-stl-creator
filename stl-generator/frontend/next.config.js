/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // Standalone build for easier deployment
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ]
  },
}

module.exports = nextConfig
