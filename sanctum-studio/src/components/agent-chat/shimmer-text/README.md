# TextShimmer Component

An animated text shimmer component powered by `motion/react` (Framer Motion) that sweeps a light reflection across text characters smoothly.

## Features
- **Dynamic Spread Calculation**: Spread scales dynamically with text length or custom configuration.
- **Polymorphic Tag Support**: Render as `p`, `span`, `h1`, `h2`, `div`, etc. via the `as` prop.
- **Light & Dark Mode Support**: Automatic CSS variable switching.
- **Custom Speed & Duration**: Configure shimmer period in seconds.

---

## Installation & Peer Dependencies

```bash
npm install motion clsx tailwind-merge
# or
pnpm add motion clsx tailwind-merge
```

---

## Usage Example

```tsx
import { TextShimmer } from "@/components/ui/shimmer-text";
// Or via modular export:
// import { TextShimmer, StatusLine } from "@/Components/shimmer-text";

export function ThinkingStatus() {
  return (
    <TextShimmer className="font-light text-base tracking-tight" duration={1.8}>
      Agent is analyzing workspace repositories...
    </TextShimmer>
  );
}
```

---

## Props

| Prop | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `children` | `string` | **Required** | Text content to shimmer. |
| `as` | `React.ElementType` | `"p"` | HTML element to render as. |
| `duration` | `number` | `2` | Duration of one shimmer cycle in seconds. |
| `spread` | `number` | `2` | Spread multiplier per character. |
| `className` | `string` | `undefined` | Additional Tailwind / CSS classes. |
