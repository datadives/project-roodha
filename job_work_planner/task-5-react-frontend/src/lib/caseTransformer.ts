/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: caseTransformer.ts
 * 
 * 1) Purpose: Utility library or API client for caseTransformer.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

/**
 * Converts snake_case string to camelCase
 */
export function toCamel(s: string): string {
  return s.replace(/([-_][a-z])/gi, ($1) => {
    return $1.toUpperCase().replace('-', '').replace('_', '')
  })
}

/**
 * Converts camelCase string to snake_case
 */
export function toSnake(s: string): string {
  return s.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

/**
 * Recursively transforms object keys
 */
export function transformKeys(obj: any, transformer: (s: string) => string): any {
  if (Array.isArray(obj)) {
    return obj.map((v) => transformKeys(v, transformer))
  } else if (obj !== null && obj.constructor === Object) {
    return Object.keys(obj).reduce(
      (result, key) => ({
        ...result,
        [transformer(key)]: transformKeys(obj[key], transformer),
      }),
      {}
    )
  }
  return obj
}

export const keysToCamel = (obj: any) => transformKeys(obj, toCamel)
export const keysToSnake = (obj: any) => transformKeys(obj, toSnake)
