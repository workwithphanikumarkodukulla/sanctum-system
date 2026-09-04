import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  try {
    return twMerge(clsx(inputs));
  } catch {
    // Fallback if twMerge/clsx is running without tailwind-merge in minimal environments
    return inputs.flat(Infinity).filter(Boolean).join(" ");
  }
}
