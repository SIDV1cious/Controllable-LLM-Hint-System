import { defineConfig, loadEnv, UserConfig } from "vite"
import react from "@vitejs/plugin-react-swc"

/**
 * Vite configuration for Streamlit React Component development
 *
 * @see https://vitejs.dev/config/ for complete Vite configuration options
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  const port = env.VITE_PORT ? parseInt(env.VITE_PORT) : 3001

  return {
    base: "./",
    plugins: [react()],
    server: {
      port,
    },
    build: {
      outDir: "build",
      // MathLive is loaded after the plain editor has rendered. This keeps the
      // first interaction responsive while avoiding a hard dependency on the
      // formula chunk for basic text input.
      chunkSizeWarningLimit: 900,
    },
  } satisfies UserConfig
})
