import { Star } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface StarRatingProps {
  value: number;
  onChange: (value: number) => void;
  max?: number;
  disabled?: boolean;
  label?: string;
}

export function StarRating({
  value,
  onChange,
  max = 5,
  disabled,
  label,
}: StarRatingProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  return (
    <div
      className="flex gap-1"
      onMouseLeave={() => setHovered(null)}
      role="group"
      aria-label={label ? `${label}の評価` : "評価"}
    >
      {Array.from({ length: max }, (_, i) => i + 1).map((star) => {
        const isActive = star <= (hovered ?? value);
        return (
          <button
            key={star}
            type="button"
            onClick={() => onChange(star)}
            onMouseEnter={() => !disabled && setHovered(star)}
            disabled={disabled}
            className={cn(
              "p-1 rounded-full transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:opacity-50 disabled:hover:scale-100",
            )}
            aria-label={`${label ? label + " " : ""}${star}点`}
            aria-pressed={star <= value}
          >
            <Star
              className={cn(
                "w-6 h-6 transition-colors",
                isActive
                  ? "fill-amber-400 text-amber-400"
                  : "text-zinc-200 fill-transparent",
              )}
            />
          </button>
        );
      })}
    </div>
  );
}
