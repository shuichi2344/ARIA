import type { NextConfig } from "next";
import path from "path";
import { config as dotenvConfig } from "dotenv";

// Load the root .env (one level up from frontend/) at config-parse time
dotenvConfig({ path: path.resolve(__dirname, "../.env") });

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname,
  },
  env: {
    // Only expose the API URL to the frontend — no secrets!
    // Supabase keys are backend-only (service role key must NEVER be client-side)
    NEXT_PUBLIC_API_URL: process.env.API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
