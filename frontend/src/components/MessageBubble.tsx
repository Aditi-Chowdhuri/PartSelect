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

// ── Inline markdown ────────────────────────────────────────────────────────────
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[([^\]]+)\]\((https?:\/\/[^\)]+)\))/g
  let last = 0, m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    if (m[2])      nodes.push(<strong key={m.index} className="font-semibold text-gray-900">{m[2]}</strong>)
    else if (m[3]) nodes.push(<em key={m.index} className="italic">{m[3]}</em>)
    else if (m[4]) nodes.push(
      <code key={m.index} className="bg-gray-100 px-1.5 py-0.5 rounded text-[11px] font-mono text-gray-800">{m[4]}</code>
    )
    else if (m[5]) nodes.push(
      <a key={m.index} href={m[6]} target="_blank" rel="noopener noreferrer"
        className="text-gray-900 underline underline-offset-2 hover:text-gray-600 break-all">{m[5]}</a>
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
  let tableRows: string[][] = []
  let inTable = false

  const flushList = (key: number) => {
    if (listItems.length) {
      nodes.push(
        <ul key={`ul-${key}`} className="list-disc list-outside pl-5 space-y-1 my-2 text-[15px] text-gray-800">
          {listItems.map((li, i) => <li key={i}>{renderInline(li)}</li>)}
        </ul>
      )
      listItems = []
    }
    if (orderedItems.length) {
      nodes.push(
        <ol key={`ol-${key}`} className="list-decimal list-outside pl-5 space-y-1 my-2 text-[15px] text-gray-800">
          {orderedItems.map((li, i) => <li key={i}>{renderInline(li)}</li>)}
        </ol>
      )
      orderedItems = []
    }
  }

  const flushTable = (key: number) => {
    if (tableRows.length < 2) { tableRows = []; inTable = false; return }
    const [header, , ...body] = tableRows
    nodes.push(
      <div key={`tbl-${key}`} className="overflow-x-auto my-3 rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>{header.map((h, i) => <th key={i} className="px-3 py-2 text-left text-xs font-semibold text-gray-600">{renderInline(h.trim())}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {body.map((row, ri) => (
              <tr key={ri} className="hover:bg-gray-50 transition-colors">
                {row.map((cell, ci) => <td key={ci} className="px-3 py-2 text-gray-700">{renderInline(cell.trim())}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
    tableRows = []; inTable = false
  }

  lines.forEach((line, i) => {
    if (/^\|/.test(line)) {
      inTable = true
      tableRows.push(line.split('|').slice(1, -1))
      return
    }
    if (inTable) { flushTable(i) }

    if (/^#{1,3} /.test(line)) {
      flushList(i)
      const level = line.match(/^(#+)/)?.[1].length ?? 1
      const content = line.replace(/^#+\s/, '')
      const cls = level === 1
        ? 'text-[17px] font-bold text-gray-900 mt-4 mb-1.5'
        : level === 2
        ? 'text-[15px] font-semibold text-gray-900 mt-3 mb-1'
        : 'text-[14px] font-semibold text-gray-800 mt-2 mb-0.5'
      nodes.push(<p key={i} className={cls}>{renderInline(content)}</p>)
    } else if (/^[-*] /.test(line)) {
      flushList(i)
      listItems.push(line.slice(2))
    } else if (/^\d+\. /.test(line)) {
      flushList(i)
      orderedItems.push(line.replace(/^\d+\.\s/, ''))
    } else if (/^---+$/.test(line)) {
      flushList(i)
      nodes.push(<hr key={i} className="my-3 border-gray-200" />)
    } else {
      flushList(i)
      if (line === '') {
        nodes.push(<div key={`sp-${i}`} className="h-2" />)
      } else {
        nodes.push(
          <p key={i} className="text-[15px] text-gray-800 leading-relaxed">
            {renderInline(line)}
          </p>
        )
      }
    }
  })
  flushList(lines.length)
  if (inTable) flushTable(lines.length)
  return <>{nodes}</>
}

// ── Typing dots ────────────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-gray-400"
          style={{ animation: `bounce-dot 1.4s ease-in-out ${i * 0.16}s infinite` }}
        />
      ))}
    </div>
  )
}

// ── Tool status row ────────────────────────────────────────────────────────────
function ToolStatusLine({ status }: { status: string }) {
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="flex gap-0.5">
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1 h-1 rounded-full bg-gray-400 inline-block"
            style={{ animation: `bounce-dot 1.4s ease-in-out ${i * 0.16}s infinite` }} />
        ))}
      </span>
      <span className="text-[13px] text-gray-500 italic">{status}</span>
    </div>
  )
}

// ── Component ──────────────────────────────────────────────────────────────────
function MessageBubble({ message, isTyping, toolStatus, responseTime, onAddToCart, onRegenerate, onRetry, isLast }: Props) {
  const isUser = message.role === 'user'

  const renderedContent = useMemo(
    () => message.content && !message.isError ? renderMarkdown(message.content) : null,
    [message.content, message.isError]
  )

  // User message — right-aligned pill
  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-2 animate-fade-in">
        <div className="max-w-[75%] sm:max-w-[65%] bg-gray-100 text-gray-900 rounded-3xl rounded-br-md px-4 py-3 text-[15px] leading-relaxed break-words">
          {message.content}
        </div>
      </div>
    )
  }

  const showLoadingState = isTyping || (!message.content && !message.parts?.length)

  return (
    <div className="px-4 py-3 animate-fade-in group">
      <div className="flex gap-3 max-w-3xl">
        {/* Avatar */}
        <div className="shrink-0 mt-1">
          <div className="w-7 h-7 rounded-full bg-brand-orange flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
            </svg>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">

          {/* Loading / tool status */}
          {showLoadingState && (
            <div className="h-7 flex items-center">
              {toolStatus
                ? <ToolStatusLine status={toolStatus} />
                : <TypingDots />
              }
            </div>
          )}

          {/* Text — clean, no bubble background */}
          {message.content && !message.isError && (
            <div className="text-gray-800 leading-relaxed">
              {renderedContent}
            </div>
          )}

          {/* Error */}
          {message.isError && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-xl px-3 py-2.5">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-red-700">{message.content}</p>
                {onRetry && (
                  <button onClick={onRetry}
                    className="mt-1.5 flex items-center gap-1 text-xs font-medium text-red-500 hover:text-red-700 transition-colors">
                    <RefreshCw className="w-3 h-3" /> Try again
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Product cards */}
          {!isTyping && message.parts && message.parts.length > 0 && (
            <div className="mt-3 flex gap-3 overflow-x-auto pb-2 scrollbar-thin -ml-1 pl-1"
              style={{ WebkitOverflowScrolling: 'touch' }}>
              {message.parts.map((part) => (
                <ProductCard key={part.part_number} part={part} onAddToCart={onAddToCart} />
              ))}
            </div>
          )}

          {/* Footer */}
          {!isTyping && !showLoadingState && (message.content || message.parts?.length) && !message.isError && (
            <div className="flex items-center gap-3 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
              {responseTime !== undefined && (
                <span className="text-[11px] text-gray-400">{responseTime.toFixed(1)}s</span>
              )}
              {isLast && onRegenerate && (
                <button onClick={onRegenerate}
                  className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 transition-colors">
                  <RefreshCw className="w-3 h-3" /> Regenerate
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default memo(MessageBubble)
