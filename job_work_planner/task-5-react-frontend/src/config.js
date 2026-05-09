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
export const REGION = env.VITE_AWS_REGION || 'us-east-1'
export const USER_POOL_ID = env.VITE_COGNITO_USER_POOL_ID || 'us-east-1_971juKyUp'
export const CLIENT_ID =
  env.VITE_COGNITO_CLIENT_ID ||
  env.VITE_COGNITO_USER_POOL_CLIENT_ID ||
  '6i2gbi9ttmv034ebau874s4cd0'
export const IS_DEV = env.MODE === 'development'

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
  COGNITO_DOMAIN: env.VITE_COGNITO_DOMAIN || 'roodha.auth.us-east-1.amazoncognito.com',
  REDIRECT_URL:
    env.VITE_S3_WEBSITE_URL ||
    'http://roodhaprodbucketstackv1-roodhaprodbucketv1709e8cd5-eyi4xpi7ilog.s3-website.ap-south-1.amazonaws.com',
  ALLOW_DEV_PASS: env.VITE_ALLOW_DEV_PASS === 'true',
  DEBUG_AUTH: env.VITE_DEBUG_AUTH === 'true',
  DEV_BYPASS_TOKEN: env.VITE_DEV_BYPASS_TOKEN || '',
  DEV_PASS_TOKEN: env.VITE_DEV_PASS_TOKEN || '',
  DEV_TENANT_ID: env.VITE_DEV_TENANT_ID || 'tenant-missing',
}

export default CONFIG
