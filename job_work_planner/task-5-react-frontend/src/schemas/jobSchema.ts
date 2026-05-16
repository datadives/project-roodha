/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: jobSchema.ts
 * 
 * 1) Purpose: Frontend core logic.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import { z } from 'zod'

export const jobPriorityEnum = z.enum(['LOW', 'MEDIUM', 'HIGH'])

export const jobCreateSchema = z.object({
  customerId: z.string().uuid('Please select a valid customer'),
  partId: z.string().uuid('Please select a valid part'),
  quantity: z.number().int().positive('Quantity must be a positive whole number'),
  dueDate: z.date().optional(),
  priority: jobPriorityEnum.default('MEDIUM'),
  jobNumber: z.string().optional()
})

export type JobCreateInput = z.infer<typeof jobCreateSchema>

// Response type derived from backend
export interface JobResponse {
  jobId: string
  jobNumber: string
  status: string
  customerId: string
  partId: string
  quantity: number
  dueDate: string | null
  priority: string
  createdAt: string
  updatedAt: string
}
