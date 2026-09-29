// BACKEND_API_URL is the deployed Flask backend (e.g. https://risksure-api.vercel.app).
// When set, browser calls to /api/* are proxied to it server-side, so the
// frontend and backend share an origin and no CORS configuration is needed.
// It is read at build time: redeploy the frontend after changing it.
const backendUrl = (process.env.BACKEND_API_URL || "https://risk-sure-od3i.vercel.app").trim().replace(/\/+$/, "")

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  async rewrites() {
    if (!backendUrl) return []
    return [{ source: "/api/:path*", destination: `${backendUrl}/:path*` }]
  },
}

export default nextConfig
