/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LOCAL_SINGLE_USER_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
declare module 'less/lib/less/functions/color.js'
declare module 'less/lib/less/tree/color.js'
