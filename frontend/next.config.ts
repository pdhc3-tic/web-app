import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {},
  // #407: a UPF passou a se chamar UFPA. Os endereços antigos continuam
  // funcionando, para não quebrar link salvo nem favorito.
  async redirects() {
    return [
      { source: "/sgp/upfs", destination: "/sgp/ufpas", permanent: true },
      { source: "/sgp/upfs/:path*", destination: "/sgp/ufpas/:path*", permanent: true },
    ];
  },
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: 500,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
};

export default nextConfig;
