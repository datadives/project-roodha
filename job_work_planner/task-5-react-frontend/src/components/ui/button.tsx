/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: button.tsx
 * 
 * 1) Purpose: React component for rendering button UI elements.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"
import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-xl text-sm font-black uppercase tracking-widest transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50 active:scale-95 select-none",
  {
    variants: {
      variant: {
        default: "bg-[#FF8C00] text-white shadow-[0_4px_0_0_#9a3412] hover:bg-[#FF9C20] active:shadow-none active:translate-y-[2px]",
        destructive:
          "border border-slate-600 bg-slate-900 text-slate-100 shadow-[0_4px_0_0_#020617] hover:border-[#FF8C00] hover:text-orange-300 active:shadow-none active:translate-y-[2px]",
        outline:
          "border-2 border-slate-700 bg-transparent text-slate-100 hover:bg-slate-800 hover:border-slate-600",
        secondary:
          "bg-slate-800 text-slate-100 shadow-[0_4px_0_0_#1e293b] hover:bg-slate-700 active:shadow-none active:translate-y-[2px]",
        ghost: "text-slate-400 hover:bg-slate-800 hover:text-slate-100",
        link: "text-[#FF8C00] underline-offset-4 hover:underline",
        industrial: "bg-slate-950 border-2 border-slate-700 text-[#FF8C00] shadow-xl hover:border-[#FF8C00] hover:text-orange-400 transition-all",
      },
      size: {
        default: "h-12 min-h-[44px] px-6", /* Industrial Touch Target Baseline */
        sm: "h-9 px-4 text-[10px]",
        lg: "h-14 min-h-[48px] px-8 text-base",
        icon: "h-12 w-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "industrial"
  size?: "default" | "sm" | "lg" | "icon"
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
