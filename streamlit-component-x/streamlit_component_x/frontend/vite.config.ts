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
      // Streamlit components are served inside an iframe. Keeping the editor as
      // one bundle avoids remote deployments getting stuck while fetching
      // secondary MathLive chunks.
      chunkSizeWarningLimit: 1400,
    },
  } satisfies UserConfig
})
