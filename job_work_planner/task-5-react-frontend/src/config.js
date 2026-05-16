/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: config.js
 * 
 * 1) Purpose: Frontend core logic.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

const env = import.meta.env

function requireEnv(name) {
  const value = env[name]
  if (!value) {
    throw new Error(`${name} is required. Set it in the frontend environment before starting Vite or building.`)
  }
  return String(value)
}

export const BASE_URL = requireEnv('VITE_API_BASE_URL').replace(/\/+$/, '')
export const REGION = requireEnv('VITE_COGNITO_REGION')
export const USER_POOL_ID = requireEnv('VITE_COGNITO_USER_POOL_ID')
export const CLIENT_ID = requireEnv('VITE_COGNITO_CLIENT_ID')
export const IS_DEV = env.MODE === 'development'
const browserOrigin = typeof window !== 'undefined' ? window.location.origin : ''

/**
 * Primary environment-switching hub for Project Roodha v1.5.
 *
 * Keep Vite environment reads centralized here so frontend modules can depend on
 * stable, descriptive config keys instead of scattering import.meta.env access
 * across authentication, API, and deployment-sensitive code paths.
 */
export const CONFIG = {
  BASE_URL,
  REGION,
  USER_POOL_ID,
  CLIENT_ID,
  IS_DEV,
  MODE: env.MODE,
  API_TIMEOUT_MS: Number(env.VITE_API_TIMEOUT_MS || 30000),
  COGNITO_DOMAIN: env.VITE_COGNITO_DOMAIN || '',
  REDIRECT_URL: env.VITE_S3_WEBSITE_URL || browserOrigin,
  ALLOW_DEV_PASS: IS_DEV && env.VITE_ALLOW_DEV_PASS === 'true',
  DEBUG_AUTH: env.VITE_DEBUG_AUTH === 'true',
  ENABLE_SELF_SIGNUP: env.VITE_ENABLE_SELF_SIGNUP === 'true',
  DEV_BYPASS_TOKEN: env.VITE_DEV_BYPASS_TOKEN || '',
  DEV_PASS_TOKEN: env.VITE_DEV_PASS_TOKEN || '',
  DEV_TENANT_ID: env.VITE_DEV_TENANT_ID || 'tenant-missing',
}

export default CONFIG
