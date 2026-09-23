import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes so that a caller's className always wins. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
