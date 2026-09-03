/**
 * Typed, validated access to Vite environment variables.
 * Import this instead of reading `import.meta.env` directly elsewhere.
 */
import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url(),
  VITE_APP_NAME: z.string().default("IntelliGrade"),
});

const parsed = envSchema.safeParse(import.meta.env);

if (!parsed.success) {
  // Fail fast and loud in development; a misconfigured env is a build-time bug.
  console.error("Invalid environment configuration:", parsed.error.flatten().fieldErrors);
  throw new Error("Invalid environment configuration. Check your .env file.");
}

export const env = parsed.data;
