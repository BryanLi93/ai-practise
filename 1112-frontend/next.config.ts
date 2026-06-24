import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 上层目录有别的 lockfile,显式锁定 Turbopack 根目录到本项目,消除推断警告
  turbopack: { root: __dirname },
};

export default nextConfig;
