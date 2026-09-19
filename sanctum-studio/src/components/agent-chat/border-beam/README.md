# BorderBeam Component

An animated glowing gradient beam that travels seamlessly along the border of any container.

## Features
- Dynamic size presets (`sm`, `md`, `lg`, `xl`) or custom pixel numbers.
- Preconfigured theme palettes (`neon`, `sunset`, `ocean`, `matrix`, `cyberpunk`).
- Custom `colorFrom` and `colorTo` hex / gradient stops.
- Configurable `duration`, `borderWidth`, `anchor`, and `delay`.

## Usage

```tsx
import { BorderBeam } from "@/Components/border-beam";

export function CardExample() {
  return (
    <div className="relative flex h-[200px] w-[300px] items-center justify-center overflow-hidden rounded-xl border bg-background p-6">
      <span className="font-semibold text-foreground">Glowing Card</span>
      <BorderBeam size={250} duration={12} delay={9} />
    </div>
  );
}
```
