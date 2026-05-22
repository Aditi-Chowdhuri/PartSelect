'use client'
import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { ShoppingCart, Trash2, ArrowUp, Phone } from 'lucide-react'
import { streamChat } from '@/lib/api'
import type { Message, CartItem, Part, ApplianceFilter } from '@/lib/types'
import MessageBubble from '@/components/MessageBubble'
import WelcomeScreen from '@/components/WelcomeScreen'
import CartSidebar from '@/components/CartSidebar'

const TOOL_LABELS: Record<string, string> = {
  search_catalog:            'Searching catalog…',
  get_part_details:          'Fetching part details…',
  check_model_compatibility: 'Checking compatibility…',
  manage_cart:               'Updating cart…',
  get_order:                 'Looking up order…',
}

const SUGGESTED_AFTER: string[] = [
  'Show me compatible models',
  'Add this part to my cart',
  'How do I install it?',
  'Find a cheaper alternative',
]

// Simple debounce hook
function useDebounce<T extends (...args: Parameters<T>) => void>(fn: T, delay: number): T {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  return useCallback(
    ((...args: Parameters<T>) => {
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => fn(...args), delay)
    }) as T,
    [fn, delay]
  )
}

export default function HomePage() {
  const [messages, setMessages]         = useState<Message[]>([])
  const [input, setInput]               = useState('')
  const [isLoading, setIsLoading]       = useState(false)
  const [toolStatus, setToolStatus]     = useState('')
  const [cartItems, setCartItems]       = useState<CartItem[]>([])
  const [cartOpen, setCartOpen]         = useState(false)
  const [applianceFilter, setApplianceFilter] = useState<ApplianceFilter>('all')
  const [showSuggestions, setShowSuggestions] = useState(false)

  const sessionId      = useRef(crypto.randomUUID())
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef    = useRef<HTMLTextAreaElement>(null)
  const startTimeRef   = useRef<number>(0)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Debounced textarea resize (avoid layout thrash on every keystroke)
  const adjustTextarea = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }, [])
  const debouncedAdjust = useDebounce(adjustTextarea, 60)

  // ── Cart operations ───────────────────────────────────────────────────────
  const handleAddToCart = useCallback((part: Part) => {
    setCartItems((prev) => {
      const existing = prev.find((i) => i.part_number === part.part_number)
      if (existing) {
        return prev.map((i) =>
          i.part_number === part.part_number ? { ...i, quantity: i.quantity + 1 } : i
        )
      }
      return [
        ...prev,
        {
          part_number: part.part_number,
          name:        part.name,
          price:       part.price,
          quantity:    1,
          url:         part.url,
        },
      ]
    })
  }, [])

  const handleRemoveFromCart = useCallback((part_number: string) => {
    setCartItems((prev) => prev.filter((i) => i.part_number !== part_number))
  }, [])

  const handleUpdateQty = useCallback((part_number: string, delta: number) => {
    setCartItems((prev) =>
      prev
        .map((i) =>
          i.part_number === part_number ? { ...i, quantity: i.quantity + delta } : i
        )
        .filter((i) => i.quantity > 0)
    )
  }, [])

  // ── Send message ──────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (text: string, priorMessages?: Message[]) => {
      const trimmed = text.trim()
      if (!trimmed || isLoading) return

      const userMsg: Message = {
        id:        crypto.randomUUID(),
        role:      'user',
        content:   trimmed,
        timestamp: new Date(),
      }
      const asstId = crypto.randomUUID()
      const asstMsg: Message = {
        id:        asstId,
        role:      'assistant',
        content:   '',
        timestamp: new Date(),
      }

      const baseMessages = priorMessages ?? messages
      setMessages([...baseMessages, userMsg, asstMsg])
      setInput('')
      setIsLoading(true)
      setShowSuggestions(false)
      startTimeRef.current = Date.now()
      if (textareaRef.current) textareaRef.current.style.height = 'auto'

      try {
        const history = [...baseMessages, userMsg].map((m) => ({ role: m.role, content: m.content }))
        const contextHistory: typeof history =
          applianceFilter !== 'all'
            ? [
                { role: 'user',      content: `[Filter: ${applianceFilter} parts only]` },
                { role: 'assistant', content: `Understood, I will only show results for ${applianceFilter} parts.` },
                ...history,
              ]
            : history

        let fullContent = ''

        for await (const chunk of streamChat(contextHistory, sessionId.current)) {
          if (chunk.type === 'tool_call') {
            setToolStatus(TOOL_LABELS[chunk.content as string] ?? 'Thinking…')
          } else if (chunk.type === 'text') {
            setToolStatus('')
            fullContent += chunk.content as string
            setMessages((prev) =>
              prev.map((m) => (m.id === asstId ? { ...m, content: fullContent } : m))
            )
          } else if (chunk.type === 'parts' && Array.isArray(chunk.content)) {
            setMessages((prev) =>
              prev.map((m) => (m.id === asstId ? { ...m, parts: chunk.content as Part[] } : m))
            )
          } else if (chunk.type === 'done') {
            setToolStatus('')
            const elapsed = (Date.now() - startTimeRef.current) / 1000
            setMessages((prev) =>
              prev.map((m) => (m.id === asstId ? { ...m, responseTime: elapsed } : m))
            )
            setShowSuggestions(true)
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Sorry, I ran into an error. Please check that the backend is running and try again.'
        setMessages((prev) =>
          prev.map((m) =>
            m.id === asstId
              ? { ...m, content: msg, isError: true }
              : m
          )
        )
      } finally {
        setIsLoading(false)
        setToolStatus('')
      }
    },
    [isLoading, messages, applianceFilter]
  )

  const handleRegenerate = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (!lastUser) return
    // Remove last assistant + last user so sendMessage re-adds the user message cleanly
    const trimmed = messages.slice(0, -2)
    sendMessage(lastUser.content, trimmed)
  }, [messages, sendMessage])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const clearChat = useCallback(() => {
    setMessages([])
    setInput('')
    setShowSuggestions(false)
  }, [])

  // ── Derived values (memoised) ─────────────────────────────────────────────
  const totalCartItems = useMemo(
    () => cartItems.reduce((sum, i) => sum + i.quantity, 0),
    [cartItems]
  )

  const lastAsstIdx = useMemo(
    () => [...messages].map((m, i) => ({ m, i })).filter(({ m }) => m.role === 'assistant').at(-1)?.i ?? -1,
    [messages]
  )

  const lastAsstHasContent = useMemo(
    () => lastAsstIdx >= 0 && !!messages[lastAsstIdx]?.content,
    [lastAsstIdx, messages]
  )

  return (
    <div className="flex flex-col h-screen bg-white overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 shrink-0 flex items-center justify-between">
        {/* Logo — matches partselect.com branding */}
        <a
          href="https://www.partselect.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2.5 hover:opacity-90 transition-opacity"
        >
          <div className="w-9 h-9 rounded-lg bg-brand-orange flex items-center justify-center shrink-0 shadow-sm">
            <svg viewBox="0 0 24 24" className="w-5 h-5 text-white fill-current">
              <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
            </svg>
          </div>
          <div>
            <span className="text-base sm:text-lg font-extrabold text-gray-900 tracking-tight">PartSelect</span>
            <p className="hidden sm:block text-[10px] text-gray-400 leading-none mt-0.5">Official Appliance Parts</p>
          </div>
        </a>

        {/* Right */}
        <div className="flex items-center gap-5">
          <a
            href="tel:18887384871"
            className="flex items-center gap-1 text-brand-orange font-bold text-sm hover:text-brand-orange-dark transition-colors"
            aria-label="Call 1-888-738-4871"
          >
            <Phone className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">1-888-738-4871</span>
          </a>

          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                title="Clear conversation"
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors rounded-lg hover:bg-gray-100"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setCartOpen(true)}
              className="relative p-2 text-gray-500 hover:text-brand-orange transition-colors rounded-lg hover:bg-gray-100"
              aria-label="Open cart"
            >
              <ShoppingCart className="w-5 h-5" />
              {totalCartItems > 0 && (
                <span className="absolute -top-1 -right-1 bg-brand-orange text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 leading-none">
                  {totalCartItems > 9 ? '9+' : totalCartItems}
                </span>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* ── Messages ───────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <WelcomeScreen
              onSelect={(q) => sendMessage(q)}
              filter={applianceFilter}
              onFilterChange={setApplianceFilter}
            />
          ) : (
            <>
              <div className="py-4">
                {messages.map((msg, idx) => (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    isTyping={isLoading && msg.role === 'assistant' && msg.content === '' && !msg.parts?.length}
                    toolStatus={isLoading && msg.role === 'assistant' && msg.content === '' ? toolStatus : ''}
                    responseTime={msg.responseTime}
                    onAddToCart={handleAddToCart}
                    onRegenerate={handleRegenerate}
                    onRetry={msg.isError ? handleRegenerate : undefined}
                    isLast={idx === lastAsstIdx}
                  />
                ))}
              </div>

              {/* Suggested follow-up chips */}
              {showSuggestions && !isLoading && lastAsstHasContent && (
                <div className="flex gap-2 flex-wrap px-4 pb-4 animate-fade-in">
                  {SUGGESTED_AFTER.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setShowSuggestions(false); sendMessage(s) }}
                      className="text-xs font-medium border border-brand-orange/40 text-brand-orange bg-orange-50 hover:bg-brand-orange hover:text-white px-3 py-1.5 rounded-full transition-all whitespace-nowrap"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              <div ref={messagesEndRef} className="h-4" />
            </>
          )}
        </div>
      </main>

      {/* ── Input ──────────────────────────────────────────────────────────── */}
      <div className="bg-white border-t border-gray-100 px-4 pt-3 pb-safe shrink-0">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 bg-white border border-gray-300 rounded-2xl px-4 py-3 focus-within:border-brand-orange focus-within:ring-1 focus-within:ring-brand-orange/30 transition-all shadow-sm">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); debouncedAdjust() }}
              onKeyDown={handleKeyDown}
              placeholder="Ask about refrigerator or dishwasher parts…"
              rows={1}
              disabled={isLoading}
              className="flex-1 resize-none bg-transparent text-sm text-gray-900 placeholder-gray-400 focus:outline-none scrollbar-thin leading-relaxed disabled:opacity-60"
              style={{ maxHeight: '120px' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all disabled:bg-gray-200 disabled:cursor-not-allowed bg-brand-orange hover:bg-brand-orange-dark active:scale-95"
              aria-label="Send"
            >
              <ArrowUp className="w-4 h-4 text-white" />
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-2">
            Specialised in refrigerator &amp; dishwasher parts · Always verify at PartSelect.com
          </p>
        </form>
      </div>

      {/* ── Cart sidebar ───────────────────────────────────────────────────── */}
      <CartSidebar
        items={cartItems}
        isOpen={cartOpen}
        onClose={() => setCartOpen(false)}
        onRemove={handleRemoveFromCart}
        onUpdateQty={handleUpdateQty}
      />
    </div>
  )
}
