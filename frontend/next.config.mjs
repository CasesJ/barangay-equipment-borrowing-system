/** @type {import('next').NextConfig} */
// API traffic is handled by app/api/proxy/[...path]/route.js. Keeping the
// proxy in a Next.js route handler makes Flask session cookies same-origin
// from the browser's perspective and avoids a browser-to-backend CORS setup.
const nextConfig = {};

export default nextConfig;
