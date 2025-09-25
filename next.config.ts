import type { NextConfig } from "next";
import createMDX from "@next/mdx";

const nextConfig: NextConfig = {
  /* config options here */
};

const withMDX = createMDX({
  // Add your options here
});

export default withMDX(nextConfig);
