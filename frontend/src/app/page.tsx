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
  check_model_compatibility: 'Checking model compatibility…',
  manage_cart:               'Updating cart…',
  get_order:                 'Looking up order…',
  find_parts_by_symptom:     'Finding parts for that symptom…',
  find_parts_by_type:        'Browsing part types…',
  find_parts_by_brand:       'Looking up brand parts…',
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

  // Load cart from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('partselect_cart')
      if (saved) setCartItems(JSON.parse(saved))
    } catch { /* ignore corrupt storage */ }
  }, [])

  // Persist cart to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('partselect_cart', JSON.stringify(cartItems))
    } catch { /* ignore quota errors */ }
  }, [cartItems])

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
        let partsBuffer: Part[] | null = null
        let textStarted = false

        for await (const chunk of streamChat(contextHistory, sessionId.current)) {
          if (chunk.type === 'tool_call') {
            setToolStatus(TOOL_LABELS[chunk.content as string] ?? 'Thinking…')
          } else if (chunk.type === 'text') {
            setToolStatus('')
            fullContent += chunk.content as string
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== asstId) return m
                // Flush buffered parts together with the first text chunk
                if (!textStarted && partsBuffer) {
                  textStarted = true
                  const flushed = partsBuffer
                  partsBuffer = null
                  return { ...m, content: fullContent, parts: flushed }
                }
                textStarted = true
                return { ...m, content: fullContent }
              })
            )
          } else if (chunk.type === 'cart_sync' && Array.isArray(chunk.content)) {
            // Claude called manage_cart — sync frontend cart to match server state
            setCartItems(chunk.content as CartItem[])
          } else if (chunk.type === 'parts' && Array.isArray(chunk.content)) {
            if (textStarted) {
              // Text already flowing — attach immediately
              setMessages((prev) =>
                prev.map((m) => (m.id === asstId ? { ...m, parts: chunk.content as Part[] } : m))
              )
            } else {
              // Hold until first text chunk so context always precedes cards
              partsBuffer = chunk.content as Part[]
            }
          } else if (chunk.type === 'done') {
            setToolStatus('')
            // Flush any parts that arrived but text never came (edge case)
            if (partsBuffer) {
              const flushed = partsBuffer
              partsBuffer = null
              setMessages((prev) =>
                prev.map((m) => (m.id === asstId ? { ...m, parts: flushed } : m))
              )
            }
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
      <header className="bg-white border-b border-gray-100 px-5 py-2.5 shrink-0 flex items-center justify-between">
        <a
          href="https://www.partselect.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <div className="w-8 h-8 rounded-lg bg-brand-orange flex items-center justify-center shrink-0">
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
            </svg>
          </div>
          <span className="text-[15px] font-bold text-gray-900 tracking-tight">PartSelect</span>
        </a>

        <div className="flex items-center gap-1">
          <a
            href="tel:18887384871"
            className="hidden sm:flex items-center gap-1 text-[13px] text-gray-500 hover:text-brand-orange transition-colors px-2 py-1.5 rounded-lg hover:bg-gray-50 mr-1"
          >
            <Phone className="w-3.5 h-3.5" />
            1-888-738-4871
          </a>
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              title="New conversation"
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
              <span className="absolute -top-0.5 -right-0.5 bg-brand-orange text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1 leading-none">
                {totalCartItems > 9 ? '9+' : totalCartItems}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* ── Messages ───────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-2xl mx-auto">
          {messages.length === 0 ? (
            <WelcomeScreen
              onSelect={(q) => sendMessage(q)}
              filter={applianceFilter}
              onFilterChange={setApplianceFilter}
            />
          ) : (
            <>
              <div className="pt-6 pb-2">
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

              {/* Suggested follow-ups */}
              {showSuggestions && !isLoading && lastAsstHasContent && (
                <div className="flex gap-2 flex-wrap pl-14 pr-4 pb-4 animate-fade-in">
                  {SUGGESTED_AFTER.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setShowSuggestions(false); sendMessage(s) }}
                      className="text-xs font-medium border border-gray-200 text-gray-600 bg-white hover:border-brand-orange hover:text-brand-orange px-3 py-1.5 rounded-full transition-all whitespace-nowrap shadow-sm"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              <div ref={messagesEndRef} className="h-6" />
            </>
          )}
        </div>
      </main>

      {/* ── Input ──────────────────────────────────────────────────────────── */}
      <div className="bg-white border-t border-gray-100 px-4 pt-3 pb-safe shrink-0">
        <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
          <div className="flex items-end gap-2.5 bg-white border border-gray-200 rounded-2xl px-4 py-3 focus-within:border-gray-400 focus-within:ring-2 focus-within:ring-gray-100 transition-all shadow-sm">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); debouncedAdjust() }}
              onKeyDown={handleKeyDown}
              placeholder="Ask about refrigerator or dishwasher parts…"
              rows={1}
              disabled={isLoading}
              className="flex-1 resize-none bg-transparent text-[15px] text-gray-900 placeholder-gray-400 focus:outline-none scrollbar-thin leading-relaxed disabled:opacity-50"
              style={{ maxHeight: '120px' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all disabled:bg-gray-200 disabled:cursor-not-allowed bg-gray-900 hover:bg-gray-700 active:scale-95"
              aria-label="Send"
            >
              <ArrowUp className="w-4 h-4 text-white" />
            </button>
          </div>
          <p className="text-center text-[11px] text-gray-400 mt-2">
            Specialised in refrigerator &amp; dishwasher parts · Always verify at{' '}
            <a href="https://www.partselect.com" target="_blank" rel="noopener noreferrer"
              className="hover:text-gray-600 transition-colors">PartSelect.com</a>
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
