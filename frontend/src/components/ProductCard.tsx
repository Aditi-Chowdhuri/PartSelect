'use client'
import { memo, useState } from 'react'
import { ShoppingCart, ExternalLink, Star, Package } from 'lucide-react'
import type { Part } from '@/lib/types'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

interface Props {
  part: Part
  onAddToCart: (part: Part) => void
}

function ProductCard({ part, onAddToCart }: Props) {
  const partUrl  = part.url || `https://www.partselect.com/${part.part_number}.htm`
  const pn       = part.part_number.replace(/\D/g, '')
  const proxyImg = pn ? `${BACKEND_URL}/image/${pn}` : ''
  const [imgSrc, setImgSrc]       = useState(proxyImg || part.image_url || '')
  const [imgFailed, setImgFailed] = useState(!proxyImg && !part.image_url)

  return (
    <div className="flex flex-col w-44 sm:w-52 shrink-0 bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden group">
      {/* Image */}
      <div className="relative w-full h-36 bg-gray-50 overflow-hidden flex items-center justify-center">
        {!imgFailed ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imgSrc}
            alt={part.name}
            loading="lazy"
            className="object-contain p-2 w-full h-full group-hover:scale-105 transition-transform duration-200"
            onError={() => {
              if (proxyImg && imgSrc === proxyImg && part.image_url && part.image_url !== proxyImg) {
                setImgSrc(part.image_url)
              } else {
                setImgFailed(true)
              }
            }}
          />
        ) : (
          <div className="flex flex-col items-center justify-center gap-1 text-gray-300">
            <Package className="w-8 h-8" />
            <span className="text-[10px]">No image</span>
          </div>
        )}
        {part.availability && (
          <span className="absolute top-2 left-2 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">
            {part.availability}
          </span>
        )}
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <div>
          <p className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">{part.name}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <span className="text-xs text-gray-400">#{part.part_number}</span>
            <span className="text-gray-300">·</span>
            <span className="text-xs bg-blue-50 text-brand-blue px-1.5 py-0.5 rounded font-medium">{part.brand}</span>
          </div>
        </div>

        {part.rating !== undefined && part.rating > 0 && (
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
            <span>{part.rating.toFixed(1)}</span>
            {part.review_count ? <span className="text-gray-400">({part.review_count})</span> : null}
          </div>
        )}

        {part.install_difficulty && (
          <p className="text-xs text-gray-500">
            Difficulty: <span className="font-medium text-gray-700">{part.install_difficulty}</span>
            {part.install_time ? ` · ${part.install_time}` : ''}
          </p>
        )}

        <div className="mt-auto pt-2 border-t border-gray-100">
          <p className="text-brand-blue font-bold text-base mb-2">${part.price.toFixed(2)}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onAddToCart(part)}
              className="flex-1 flex items-center justify-center gap-1.5 bg-brand-orange hover:bg-brand-orange-dark text-white text-xs font-semibold py-2 px-2 rounded-lg transition-colors"
            >
              <ShoppingCart className="w-3 h-3" />
              Add to Cart
            </button>
            <a
              href={partUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 text-gray-400 hover:text-brand-blue transition-colors rounded-lg hover:bg-gray-100"
              title="View on PartSelect"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default memo(ProductCard)
