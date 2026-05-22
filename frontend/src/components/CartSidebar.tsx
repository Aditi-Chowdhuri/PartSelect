'use client'
import { memo } from 'react'
import { X, ShoppingCart, ExternalLink, Plus, Minus } from 'lucide-react'
import type { CartItem } from '@/lib/types'

interface Props {
  items:       CartItem[]
  isOpen:      boolean
  onClose:     () => void
  onRemove:    (part_number: string) => void
  onUpdateQty: (part_number: string, delta: number) => void
}

function CartSidebar({ items, isOpen, onClose, onRemove, onUpdateQty }: Props) {
  const subtotal    = items.reduce((sum, i) => sum + i.price * i.quantity, 0)
  const itemCount   = items.reduce((sum, i) => sum + i.quantity, 0)

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 backdrop-blur-sm transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        className={`fixed top-0 right-0 h-full w-full sm:w-[340px] bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2">
            <ShoppingCart className="w-5 h-5 text-brand-orange" />
            <h2 className="font-semibold text-gray-900">
              Cart
              {itemCount > 0 && (
                <span className="ml-1.5 text-sm font-normal text-gray-500">({itemCount} item{itemCount !== 1 ? 's' : ''})</span>
              )}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close cart"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-y-auto scrollbar-thin py-3 px-5">
          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-12 gap-3">
              <ShoppingCart className="w-12 h-12 text-gray-200" />
              <p className="text-gray-400 text-sm">Your cart is empty</p>
              <p className="text-gray-400 text-xs">Add parts from the chat to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <div
                  key={item.part_number}
                  className="bg-gray-50 rounded-xl p-3 flex gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 leading-snug line-clamp-2">{item.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">#{item.part_number}</p>
                    <p className="text-sm font-bold text-brand-blue mt-1">
                      ${(item.price * item.quantity).toFixed(2)}
                    </p>
                  </div>

                  <div className="flex flex-col items-end justify-between shrink-0">
                    {/* Remove */}
                    <button
                      onClick={() => onRemove(item.part_number)}
                      className="p-1 text-gray-300 hover:text-red-400 transition-colors"
                      title="Remove item"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>

                    {/* Quantity controls */}
                    <div className="flex items-center gap-1 bg-white border border-gray-200 rounded-lg overflow-hidden">
                      <button
                        onClick={() => onUpdateQty(item.part_number, -1)}
                        className="w-7 h-7 flex items-center justify-center text-gray-500 hover:bg-gray-100 transition-colors"
                        aria-label="Decrease quantity"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-6 text-center text-sm font-medium text-gray-900">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() => onUpdateQty(item.part_number, +1)}
                        className="w-7 h-7 flex items-center justify-center text-gray-500 hover:bg-gray-100 transition-colors"
                        aria-label="Increase quantity"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div className="border-t border-gray-200 px-5 py-4 space-y-3 shrink-0">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Subtotal ({itemCount} item{itemCount !== 1 ? 's' : ''})</span>
              <span className="font-bold text-lg text-gray-900">${subtotal.toFixed(2)}</span>
            </div>
            <a
              href="https://www.partselect.com/cart"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full bg-brand-orange hover:bg-brand-orange-dark text-white font-semibold py-3 px-4 rounded-xl transition-colors shadow-sm"
            >
              Checkout on PartSelect
              <ExternalLink className="w-4 h-4" />
            </a>
            <p className="text-xs text-gray-400 text-center">
              You will be redirected to PartSelect to complete your purchase
            </p>
          </div>
        )}
      </aside>
    </>
  )
}

export default memo(CartSidebar)
