'use client'

interface Props {
  suggestions: string[]
  onSelect: (s: string) => void
}

export default function SuggestedChips({ suggestions, onSelect }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin px-4">
      {suggestions.map((s) => (
        <button
          key={s}
          onClick={() => onSelect(s)}
          className="shrink-0 text-xs font-medium border border-brand-blue text-brand-blue bg-white hover:bg-brand-blue-light px-3 py-1.5 rounded-full transition-colors whitespace-nowrap"
        >
          {s}
        </button>
      ))}
    </div>
  )
}
