import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Prevent Next.js from bundling pdf-parse / pdfjs-dist in server routes.
  // pdfjs-dist internally imports a pdf.worker.mjs whose path is resolved at
  // runtime; when Turbopack/webpack inlines it the resolved path breaks.
  // Keeping these as native Node modules avoids the "Cannot find module
  // pdf.worker.mjs" error in /api/extract-labs.
  serverExternalPackages: ["pdf-parse", "pdfjs-dist"],
};

export default nextConfig;
