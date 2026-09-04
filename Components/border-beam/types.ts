export type BorderBeamSize = "sm" | "md" | "lg" | "xl" | number;
export type BorderBeamTheme = "default" | "neon" | "sunset" | "ocean" | "matrix" | "cyberpunk";
export type BorderBeamColorVariant = "default" | "primary" | "secondary" | "accent" | "rainbow";

export interface BorderBeamProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
  size?: BorderBeamSize;
  duration?: number;
  borderWidth?: number;
  anchor?: number;
  colorFrom?: string;
  colorTo?: string;
  delay?: number;
  theme?: BorderBeamTheme;
  colorVariant?: BorderBeamColorVariant;
  reverse?: boolean;
}
