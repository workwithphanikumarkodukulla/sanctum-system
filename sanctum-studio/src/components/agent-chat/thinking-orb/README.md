# ThinkingOrb Component

Replaces the traditional loading spinner in an AI "thinking" state with hand-tuned, organic animated orb states.

## Features
- **9 Hand-Tuned States**: `"working"`, `"searching"`, `"solving"`, `"listening"`, `"connecting"`, `"weaving"`, `"composing"`, `"breathing"`, `"shaping"`.
- **Zero Runtime Dependencies**: Pure React 18+ and CSS animations.
- **Dual Scale Optimization**: Hand-tuned for `size={64}` (chat avatar scale) and `size={20}` (inline text scale).
- **Speed Multiplier**: Adjust the animation clock with the `speed` prop.
- **Dark & Light Mode Support**: Tuned palettes for both color schemes.
- **Freeze State**: `paused` boolean to freeze the animation gracefully.

---

## Installation & Usage

```tsx
import { ThinkingOrb } from "@/Components/thinking-orb";

export function ThinkingDemo() {
  return (
    <div className="flex items-center gap-4 p-6">
      {/* Chat Avatar Scale */}
      <ThinkingOrb state="searching" size={64} dark={true} />

      {/* Inline Text Scale */}
      <div className="flex items-center gap-2">
        <ThinkingOrb state="working" size={20} />
        <span className="text-sm text-muted-foreground">Thinking...</span>
      </div>
    </div>
  );
}
```

---

## Props

| Prop | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `state` | `"working" \| "searching" \| "solving" \| "listening" \| "connecting" \| "weaving" \| "composing" \| "breathing" \| "shaping"` | `"working"` | The AI cognitive state being visualized. |
| `size` | `20 \| 64 \| number` | `64` | The size of the orb in pixels. |
| `speed` | `number` | `1` | Animation speed clock multiplier. |
| `dark` | `boolean` | `true` | Selects light or dark mode tuned palette. |
| `paused` | `boolean` | `false` | Freezes the animation. |
