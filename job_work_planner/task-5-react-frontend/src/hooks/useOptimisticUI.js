/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: useOptimisticUI.js
 * 
 * 1) Purpose: Custom React hook for state management (useOptimisticUI).
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { useState, useCallback } from 'react'
import { toast } from 'react-hot-toast'

/**
 * Custom hook for optimistic UI updates.
 * @template T - The state type
 * @param {T} initialState - Initial data from the server
 * @returns {{ data: T, mutate: (updater: (prev: T) => T, action: () => Promise<any>) => Promise<void>, loading: boolean }}
 */
export function useOptimisticUI(initialState) {
  const [data, setData] = useState(initialState)
  const [loading, setLoading] = useState(false)

  const mutate = useCallback(async (optimisticUpdater, asyncAction) => {
    const previousData = data
    
    // 1. Update state immediately (Optimistic)
    setData(optimisticUpdater)
    setLoading(true)

    try {
      // 2. Perform background action
      await asyncAction()
      // Success: Stay in the new state, but we might want to refresh from server here if the response has data
    } catch (error) {
      // 3. Rollback on failure
      console.error('[OptimisticUI] Action failed, rolling back:', error)
      setData(previousData)
      toast.error(error.message || 'Action failed. Reverting changes.')
    } finally {
      setLoading(false)
    }
  }, [data])

  return {
    data,
    setData, // Exposed for manual syncs
    mutate,
    loading
  }
}

export default useOptimisticUI
