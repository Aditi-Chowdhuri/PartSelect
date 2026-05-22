'use client'
import { memo, useMemo } from 'react'
import { RefreshCw, AlertCircle } from 'lucide-react'
import type { Message, Part } from '@/lib/types'
import ProductCard from './ProductCard'

interface Props {
  message:       Message
  isTyping?:     boolean
  toolStatus?:   string
  responseTime?: number
  onAddToCart:   (part: Part) => void
  onRegenerate?: () => void
  onRetry?:      () => void
  isLast?:       boolean
}

// ── Inline markdown renderer ──────────────────────────────────────────────────
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[([^\]]+)\]\((https?:\/\/[^\)]+)\))/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    if (m[2])      nodes.push(<strong key={m.index} className="font-semibold">{m[2]}</strong>)
    else if (m[3]) nodes.push(<em key={m.index}>{m[3]}</em>)
    else if (m[4]) nodes.push(
      <code key={m.index} className="bg-gray-100 px-1.5 py-0.5 rounded text-[11px] font-mono text-gray-800">
        {m[4]}
      </code>
    )
    else if (m[5]) nodes.push(
      <a key={m.index} href={m[6]} target="_blank" rel="noopener noreferrer"
        className="text-brand-blue underline underline-offset-2 hover:text-brand-blue-dark break-all">
        {m[5]}
      </a>
    )
    last = m.index + m[0].length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  let listItems: string[] = []
  let orderedItems: string[] = []

  const flushList = (key: number) => {
    if (listItems.length) {
      nodes.push(
        <ul key={`ul-${key}`} className="list-disc list-inside space-y-1 my-1.5 text-gray-700 text-sm">
          {listItems.map((li, i) => <li key={i}>{renderInline(li)}</li>)}
        </ul>
      )
      listItems = []
    }
    if (orderedItems.length) {
      nodes.push(
        <ol key={`ol-${key}`} className="list-decimal list-inside space-y-1 my-1.5 text-gray-700 text-sm">
          {orderedItems.map((li, i) => <li key={i}>{renderInline(li)}</li>)}
        </ol>
      )
      orderedItems = []
    }
  }

  lines.forEach((line, i) => {
    if (/^#{1,3} /.test(line)) {
      flushList(i)
      const level = line.match(/^(#+)/)?.[1].length ?? 1
      const content = line.replace(/^#+\s/, '')
      const cls = level === 1
        ? 'text-base font-bold text-gray-900 mt-3 mb-1'
        : level === 2
        ? 'text-sm font-semibold text-gray-800 mt-2 mb-1'
        : 'text-sm font-semibold text-gray-700 mt-1'
      nodes.push(<p key={i} className={cls}>{renderInline(content)}</p>)
    } else if (/^[-*] /.test(line)) {
      flushList(i); // flush ordered if switching
      listItems.push(line.slice(2))
    } else if (/^\d+\. /.test(line)) {
      flushList(i)
      orderedItems.push(line.replace(/^\d+\.\s/, ''))
    } else if (/^---+$/.test(line)) {
      flushList(i)
      nodes.push(<hr key={i} className="my-2 border-gray-200" />)
    } else {
      flushList(i)
      if (line === '') {
        nodes.push(<div key={`sp-${i}`} className="h-1.5" />)
      } else {
        nodes.push(
          <p key={i} className="text-sm text-gray-800 leading-relaxed">
            {renderInline(line)}
          </p>
        )
      }
    }
  })
  flushList(lines.length)
  return <div className="space-y-0.5">{nodes}</div>
}

// ── Typing animation ──────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-gray-300 inline-block"
          style={{ animation: `bounce-dot 1.2s ease-in-out ${i * 0.2}s infinite` }}
        />
      ))}
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────
function MessageBubble({ message, isTyping, toolStatus, responseTime, onAddToCart, onRegenerate, onRetry, isLast }: Props) {
  const isUser = message.role === 'user'

  const renderedContent = useMemo(
    () => message.content && !message.isError ? renderMarkdown(message.content) : null,
    [message.content, message.isError]
  )

  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-3 animate-fade-in">
        <div className="max-w-[85%] sm:max-w-[78%] bg-[#1b3875] text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-sm break-words">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 px-4 py-3 animate-fade-in group">
      {/* Avatar */}
      <div className="shrink-0 mt-0.5">
        <div className="w-8 h-8 rounded-full bg-brand-orange flex items-center justify-center text-sm font-bold text-white shadow-sm">
          P
        </div>
      </div>

      {/* Assistant content */}
      <div className="flex-1 min-w-0">
        {/* Thinking / tool status */}
        {(isTyping || (!message.content && !message.parts?.length)) && (
          <div className="text-sm text-gray-400">
            {toolStatus
              ? <span className="italic animate-pulse">{toolStatus}</span>
              : <TypingDots />
            }
          </div>
        )}

        {/* Text */}
        {message.content && !message.isError && (
          <div className="bg-gray-50 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
            {renderedContent}
          </div>
        )}

        {/* Error state */}
        {message.isError && (
          <div className="bg-red-50 border border-red-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-red-700">{message.content}</p>
                {onRetry && (
                  <button
                    onClick={onRetry}
                    className="mt-2 flex items-center gap-1.5 text-xs font-medium text-red-500 hover:text-red-700 transition-colors"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Try again
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Product cards */}
        {!isTyping && message.parts && message.parts.length > 0 && (
          <div className="mt-3 flex gap-3 overflow-x-auto pb-2 scrollbar-thin -mx-1 px-1" style={{ WebkitOverflowScrolling: 'touch' }}>
            {message.parts.map((part) => (
              <ProductCard key={part.part_number} part={part} onAddToCart={onAddToCart} />
            ))}
          </div>
        )}

        {/* Footer: response time + regenerate */}
        {!isTyping && message.content && !message.isError && (
          <div className="flex items-center gap-4 mt-2 pl-1">
            {responseTime !== undefined && (
              <span className="text-[11px] text-gray-400">
                {responseTime.toFixed(1)}s
              </span>
            )}
            {isLast && onRegenerate && (
              <button
                onClick={onRegenerate}
                className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 transition-colors opacity-0 group-hover:opacity-100"
              >
                <RefreshCw className="w-3 h-3" />
                Regenerate
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default memo(MessageBubble)
