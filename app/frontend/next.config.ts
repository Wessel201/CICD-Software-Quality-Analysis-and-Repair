import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Turbopack (Next.js 16+ default dev server)
  turbopack: {
    rules: {
      "**/*.py": {
        loaders: ["raw-loader"],
        as: "*.js",
      },
    },
  },
  // Webpack (used for `next build`)
  webpack: (config) => {
    config.module.rules.push({
      test: /\.py$/,
      type: "asset/source",
    });
    return config;
  },
};

export default nextConfig;
