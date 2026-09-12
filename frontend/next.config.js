/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces a self-contained .next/standalone build with only the
  // production node_modules it actually needs traced in — the
  // difference between a multi-hundred-MB image (full node_modules) and
  // a genuinely small one, and the reason the Dockerfile below can be a
  // simple multi-stage build instead of shipping the whole repo.
  output: "standalone",
};

module.exports = nextConfig;
