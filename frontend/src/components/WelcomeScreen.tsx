'use client'
import { memo } from 'react'
import type { ApplianceFilter } from '@/lib/types'

const CAPABILITIES = [
  { icon: '🔍', text: 'Find parts by symptom, name, or part number' },
  { icon: '✅', text: 'Check compatibility with your appliance model' },
  { icon: '🛒', text: 'Add parts to cart and checkout on PartSelect' },
  { icon: '🎥', text: 'Get installation videos and repair guides' },
  { icon: '📦', text: 'Look up order status and tracking' },
]

const QUERIES_BY_FILTER: Record<ApplianceFilter, { label: string; query: string }[]> = {
  all: [
    { label: 'Ice maker not working',        query: 'The ice maker on my Whirlpool fridge is not working. How can I fix it?' },
    { label: 'Dishwasher not draining',      query: 'My dishwasher is not draining. What parts should I check?' },
    { label: 'Check part compatibility',     query: 'Is part PS11752778 compatible with my WDT780SAEM1 model?' },
    { label: 'Find a door gasket',           query: 'I need a replacement door gasket for my GE refrigerator' },
  ],
  refrigerator: [
    { label: 'Ice maker not working',        query: 'The ice maker on my Whirlpool fridge is not working. How can I fix it?' },
    { label: 'Fridge not cooling',           query: 'My refrigerator is not cooling properly. What parts could cause this?' },
    { label: 'Water filter replacement',     query: 'I need to replace the water filter on my Samsung refrigerator' },
    { label: 'Door seal / gasket',           query: 'I need a replacement door gasket for my GE refrigerator' },
  ],
  dishwasher: [
    { label: 'Dishwasher not draining',      query: 'My dishwasher is not draining. What parts should I check?' },
    { label: 'Dishes not getting clean',     query: 'My Bosch dishwasher is not cleaning dishes well. What could be wrong?' },
    { label: 'Dishwasher leaking',           query: 'My dishwasher is leaking water from the door. What part do I need?' },
    { label: 'Control panel not working',    query: 'The control panel on my Whirlpool dishwasher stopped responding' },
  ],
}

const FILTER_META: Record<ApplianceFilter, { label: string; icon: string; description: string; color: string }> = {
  all: {
    label:       'All Parts',
    icon:        '🔧',
    description: 'Searching across all refrigerator and dishwasher parts.',
    color:       'text-gray-600',
  },
  refrigerator: {
    label:       'Refrigerator',
    icon:        '🧊',
    description: 'AI responses will be filtered to refrigerator parts only.',
    color:       'text-blue-600',
  },
  dishwasher: {
    label:       'Dishwasher',
    icon:        '🍽️',
    description: 'AI responses will be filtered to dishwasher parts only.',
    color:       'text-teal-600',
  },
}

const FILTERS: { label: string; value: ApplianceFilter; icon: string }[] = [
  { label: 'All Parts',    value: 'all',          icon: '🔧' },
  { label: 'Refrigerator', value: 'refrigerator', icon: '🧊' },
  { label: 'Dishwasher',   value: 'dishwasher',   icon: '🍽️' },
]

interface Props {
  onSelect:       (query: string) => void
  filter:         ApplianceFilter
  onFilterChange: (f: ApplianceFilter) => void
}

function WelcomeScreen({ onSelect, filter, onFilterChange }: Props) {
  const meta    = FILTER_META[filter]
  const queries = QUERIES_BY_FILTER[filter]

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 animate-fade-in">
      {/* Greeting */}
      <div className="mb-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-brand-orange flex items-center justify-center text-2xl font-bold text-white shadow-lg mx-auto mb-4">
          P
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Hi, I&apos;m your PartSelect Assistant
        </h1>
        <p className="text-gray-500 text-sm leading-relaxed max-w-md mx-auto">
          I specialize in refrigerator and dishwasher parts — finding the right part,
          checking compatibility, and guiding you through repairs.
        </p>
      </div>

      {/* Filter pills */}
      <div className="mb-2 flex justify-center gap-2">
        {FILTERS.map(({ label, value, icon }) => (
          <button
            key={value}
            onClick={() => onFilterChange(value)}
            className={`px-4 py-2 rounded-full text-sm font-medium border transition-all ${
              filter === value
                ? 'bg-brand-orange text-white border-brand-orange shadow-sm scale-105'
                : 'bg-white text-gray-600 border-gray-200 hover:border-brand-orange hover:text-brand-orange'
            }`}
          >
            {icon} {label}
          </button>
        ))}
      </div>

      {/* Filter effect description */}
      <p className={`text-center text-xs mb-6 font-medium ${meta.color}`}>
        {filter !== 'all' && <span className="mr-1">✦</span>}
        {meta.description}
      </p>

      {/* Example queries — change with filter */}
      <div className="mb-8">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          {filter === 'all' ? 'Try asking' : `Try asking about ${meta.label.toLowerCase()} parts`}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {queries.map(({ label, query }) => (
            <button
              key={label}
              onClick={() => onSelect(query)}
              className="text-left px-4 py-3 rounded-xl border border-gray-200 bg-white hover:border-brand-orange hover:bg-orange-50 transition-all group text-sm text-gray-700 font-medium shadow-sm"
            >
              <span className="group-hover:text-brand-orange transition-colors">{label}</span>
              <p className="text-xs text-gray-400 mt-0.5 font-normal line-clamp-1 group-hover:text-orange-400">
                {query}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Capabilities */}
      <div className="bg-gray-50 rounded-2xl p-5">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">What I can do</p>
        <ul className="space-y-2">
          {CAPABILITIES.map(({ icon, text }) => (
            <li key={text} className="flex items-center gap-3 text-sm text-gray-600">
              <span className="text-base shrink-0">{icon}</span>
              {text}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default memo(WelcomeScreen)
