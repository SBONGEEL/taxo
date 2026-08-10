/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** عنوان الخلفية — المنفذ 8001 محلياً (انظر `docker-compose.yml`). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
