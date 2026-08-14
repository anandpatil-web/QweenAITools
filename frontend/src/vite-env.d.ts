/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend API base URL. Unset in local dev (falls back to "/api", proxied
   *  by Vite). Set to the hosted backend origin in production, e.g.
   *  "https://qween-backend.onrender.com/api". */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
