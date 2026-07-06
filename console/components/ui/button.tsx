import type { ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3 text-[13px] font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-[var(--accent)] text-[#11100d] hover:bg-[var(--accent-hi)]",
        secondary:
          "border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text)] hover:bg-white/[.04]",
        ghost: "text-[var(--text-mut)] hover:bg-white/[.04] hover:text-[var(--text)]",
      },
    },
    defaultVariants: {
      variant: "secondary",
    },
  },
);

export function Button({
  className,
  variant,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>) {
  return (
    <button className={cn(buttonVariants({ variant }), className)} {...props} />
  );
}
