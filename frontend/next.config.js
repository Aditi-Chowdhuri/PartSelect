/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [{ hostname: 'www.partselect.com' }],
  },
}

module.exports = nextConfig
