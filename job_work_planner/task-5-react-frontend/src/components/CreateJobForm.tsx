/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: CreateJobForm.tsx
 * 
 * 1) Purpose: React component for rendering CreateJobForm UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React, { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'react-hot-toast'
import Loader2 from 'lucide-react/dist/esm/icons/loader-2.js'
import CalendarIcon from 'lucide-react/dist/esm/icons/calendar.js'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { authenticatedFetch } from '@/lib/authenticatedFetch'
import { jobCreateSchema, type JobCreateInput, type JobResponse } from '@/schemas/jobSchema'
import { cn } from '@/lib/utils'

interface Customer {
  customerId: string
  name: string
}

interface Part {
  partId: string
  partNumber: string
}

export const CreateJobForm: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [parts, setParts] = useState<Part[]>([])
  const [isLoadingMasterData, setIsLoadingMasterData] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors }
  } = useForm<JobCreateInput>({
    resolver: zodResolver(jobCreateSchema),
    defaultValues: {
      priority: 'MEDIUM',
      quantity: 1
    }
  })

  const selectedDate = watch('dueDate')

  // 1. Fetch Master Data for dropdowns
  useEffect(() => {
    const loadMasterData = async () => {
      try {
        const [customerData, partData] = await Promise.all([
          authenticatedFetch<Customer[]>('master-data/customers'),
          authenticatedFetch<Part[]>('master-data/parts')
        ])
        setCustomers(customerData)
        setParts(partData)
      } catch (error) {
        toast.error('Failed to load customers or parts. Please refresh.')
        console.error('Master data load error:', error)
      } finally {
        setIsLoadingMasterData(false)
      }
    }

    loadMasterData()
  }, [])

  // 2. Form Submission Handler
  const onSubmit = async (data: JobCreateInput) => {
    setIsSubmitting(true)
    try {
      // Directives: Payload is automatically transformed to snake_case by authenticatedFetch
      const response = await authenticatedFetch<JobResponse>('jobs', {
        method: 'POST',
        body: JSON.stringify(data)
      })

      toast.success(`Job Created Successfully: ${response.jobNumber}`)
      reset()
    } catch (error: any) {
      const detail = error.detail || 'Could not create job. Please try again.'
      toast.error(detail)
      console.error('Job creation error:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="mx-auto w-full max-w-2xl overflow-hidden industrial-shadow">
      <CardHeader className="bg-slate-900 border-b border-slate-800 p-8">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Production Floor</p>
            <CardTitle className="mt-2 text-3xl font-bold text-white tracking-tight">Create New Job</CardTitle>
          </div>
          <div className="h-12 w-12 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center">
            <CalendarIcon className="text-slate-400 h-6 w-6" />
          </div>
        </div>
      </CardHeader>
      
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="p-8 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Customer Selection */}
            <div className="space-y-2">
              <Label htmlFor="customerId" className="text-slate-600 font-semibold uppercase tracking-wider text-[10px]">Customer</Label>
              <Select 
                id="customerId"
                disabled={isLoadingMasterData}
                className={cn(errors.customerId && "border-orange-500")}
                {...register('customerId')}
              >
                <option value="">Select a customer</option>
                {customers.map(c => (
                  <option key={c.customerId} value={c.customerId}>{c.name}</option>
                ))}
              </Select>
              {errors.customerId && <p className="text-orange-400 text-xs italic">{errors.customerId.message}</p>}
            </div>

            {/* Part Selection */}
            <div className="space-y-2">
              <Label htmlFor="partId" className="text-slate-600 font-semibold uppercase tracking-wider text-[10px]">Part / Item Number</Label>
              <Select 
                id="partId"
                disabled={isLoadingMasterData}
                className={cn(errors.partId && "border-orange-500")}
                {...register('partId')}
              >
                <option value="">Select a part</option>
                {parts.map(p => (
                  <option key={p.partId} value={p.partId}>{p.partNumber}</option>
                ))}
              </Select>
              {errors.partId && <p className="text-orange-400 text-xs italic">{errors.partId.message}</p>}
            </div>

            {/* Quantity Input */}
            <div className="space-y-2">
              <Label htmlFor="quantity" className="text-slate-600 font-semibold uppercase tracking-wider text-[10px]">Production Quantity</Label>
              <Input 
                id="quantity"
                type="number"
                min="1"
                placeholder="e.g. 500"
                className={cn("h-11 rounded-xl font-mono tabular-nums", errors.quantity && "border-orange-500")}
                {...register('quantity', { valueAsNumber: true })}
              />
              {errors.quantity && <p className="text-orange-400 text-xs italic">{errors.quantity.message}</p>}
            </div>

            {/* Priority Selection */}
            <div className="space-y-2">
              <Label htmlFor="priority" className="text-slate-600 font-semibold uppercase tracking-wider text-[10px]">Job Priority</Label>
              <Select 
                id="priority"
                className="h-11 rounded-xl"
                {...register('priority')}
              >
                <option value="LOW">Low - General</option>
                <option value="MEDIUM">Medium - Standard</option>
                <option value="HIGH">High - Urgent</option>
              </Select>
            </div>

            {/* Due Date Picker (Native for Simplicity & Touch Reliability) */}
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="dueDate" className="text-slate-600 font-semibold uppercase tracking-wider text-[10px]">Requested Completion Date</Label>
              <Input 
                id="dueDate"
                type="date"
                className="h-11 rounded-xl w-full"
                onChange={(e) => setValue('dueDate', e.target.value ? new Date(e.target.value) : undefined)}
              />
              {selectedDate && (
                <p className="text-xs text-slate-500 mt-1 italic">
                  Formatted: <span className="font-mono tabular-nums">{format(selectedDate, 'PPP')}</span>
                </p>
              )}
            </div>
          </div>
        </CardContent>

        <CardFooter className="bg-slate-50 border-t border-slate-100 p-8 flex justify-end">
          <Button 
            type="submit" 
            disabled={isSubmitting || isLoadingMasterData}
            variant="default"
            size="lg"
            className="w-full md:w-auto px-10"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Processing...
              </>
            ) : (
              'Release to Production'
            )}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
