export type BorderBeamSize = "sm" | "md" | "lg" | "xl" | number;
export type BorderBeamTheme = "default" | "neon" | "sunset" | "ocean" | "matrix" | "cyberpunk" | "sanctum" | "antigravity" | "iridescent";
export type BorderBeamColorVariant = "default" | "primary" | "secondary" | "accent" | "rainbow" | "sanctum" | "antigravity" | "iridescent";


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
