import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
};

const paddingClass = {
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
} as const;

export function Card({ children, className = "", padding = "md" }: CardProps) {
  return (
    <div
      className={`rounded-2xl border border-zinc-200/80 bg-white shadow-sm ${paddingClass[padding]} ${className}`}
    >
      {children}
    </div>
  );
}
