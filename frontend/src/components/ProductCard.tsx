'use client'
import { memo } from 'react'
import { ShoppingCart, ExternalLink, Star } from 'lucide-react'
import type { Part } from '@/lib/types'

interface Props {
  part: Part
  onAddToCart: (part: Part) => void
}

function ProductCard({ part, onAddToCart }: Props) {
  const pn      = part.part_number.replace(/\D/g, '')
  const partUrl = part.url || `https://www.partselect.com/PS${pn}.htm`

  return (
    <div className="w-52 shrink-0 bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300 hover:shadow-sm transition-all duration-200">

      {/* Name */}
      <p className="text-sm font-semibold text-gray-900 leading-snug line-clamp-2 mb-1.5">{part.name}</p>

      {/* Part number + brand */}
      <div className="flex items-center gap-1.5 flex-wrap mb-2">
        <span className="text-xs font-mono text-gray-400">{part.part_number}</span>
        {part.brand && (
          <>
            <span className="text-gray-200 select-none">·</span>
            <span className="text-xs text-gray-500">{part.brand}</span>
          </>
        )}
      </div>

      {/* Rating */}
      {part.rating !== undefined && part.rating > 0 && (
        <div className="flex items-center gap-1 mb-2">
          <Star className="w-3 h-3 fill-gray-400 text-gray-400" />
          <span className="text-xs text-gray-500">{part.rating.toFixed(1)}</span>
          {part.review_count ? (
            <span className="text-xs text-gray-400">({part.review_count})</span>
          ) : null}
        </div>
      )}

      {/* Install info */}
      {part.install_difficulty && (
        <p className="text-xs text-gray-400 mb-2">
          {part.install_difficulty}{part.install_time ? ` · ${part.install_time}` : ''}
        </p>
      )}

      {/* Price + actions */}
      <div className="pt-3 border-t border-gray-100 mt-2">
        <p className="text-base font-bold text-gray-900 mb-2.5">${part.price.toFixed(2)}</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onAddToCart(part)}
            className="flex-1 flex items-center justify-center gap-1.5 bg-brand-orange hover:bg-brand-orange-dark text-white text-xs font-semibold py-2 px-3 rounded-lg transition-colors"
          >
            <ShoppingCart className="w-3 h-3" />
            Add to cart
          </button>
          <a
            href={partUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="View on PartSelect"
            className="flex items-center justify-center w-8 h-8 rounded-lg border border-gray-200 text-gray-400 hover:text-gray-700 hover:border-gray-300 transition-colors shrink-0"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  )
}

export default memo(ProductCard)
