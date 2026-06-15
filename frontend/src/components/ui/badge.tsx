import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-gradient-to-r from-blue-600 to-purple-600 text-white",
        secondary:
          "border-transparent bg-[var(--sidebar-toggle-bg)] text-[var(--foreground-color)]",
        destructive:
          "border-transparent bg-red-600/20 text-red-400 border-red-500/30",
        outline:
          "border-[var(--card-border)] text-[var(--sidebar-text-muted)]",
        success:
          "border-transparent bg-emerald-600/20 text-emerald-400 border-emerald-500/30",
        warning:
          "border-transparent bg-amber-600/20 text-amber-400 border-amber-500/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
