'use client'
import { memo } from 'react'
import { Search, CheckCircle2, ShoppingCart, Wrench, Package } from 'lucide-react'
import type { ApplianceFilter } from '@/lib/types'

const CAPABILITIES = [
  { Icon: Search,        text: 'Find parts by symptom, name, or part number' },
  { Icon: CheckCircle2,  text: 'Check compatibility with your appliance model' },
  { Icon: ShoppingCart,  text: 'Add parts to cart and checkout on PartSelect' },
  { Icon: Wrench,        text: 'Get installation guides and repair help' },
  { Icon: Package,       text: 'Look up order status and tracking' },
]

const QUERIES_BY_FILTER: Record<ApplianceFilter, { label: string; query: string }[]> = {
  all: [
    { label: 'Ice maker not working',    query: 'The ice maker on my Whirlpool fridge is not working. How can I fix it?' },
    { label: 'Dishwasher not draining',  query: 'My dishwasher is not draining. What parts should I check?' },
    { label: 'Check part compatibility', query: 'What parts are compatible with model 25344352401?' },
    { label: 'Find a door gasket',       query: 'I need a replacement door gasket for my GE refrigerator' },
  ],
  refrigerator: [
    { label: 'Ice maker not working',   query: 'The ice maker on my Whirlpool fridge is not working. How can I fix it?' },
    { label: 'Fridge not cooling',      query: 'My refrigerator is not cooling properly. What parts could cause this?' },
    { label: 'Water filter replacement',query: 'I need to replace the water filter on my Samsung refrigerator' },
    { label: 'Door seal / gasket',      query: 'I need a replacement door gasket for my GE refrigerator' },
  ],
  dishwasher: [
    { label: 'Dishwasher not draining', query: 'My dishwasher is not draining. What parts should I check?' },
    { label: 'Dishes not getting clean',query: 'My Bosch dishwasher is not cleaning dishes well. What could be wrong?' },
    { label: 'Dishwasher leaking',      query: 'My dishwasher is leaking water from the door. What part do I need?' },
    { label: 'Control panel not working',query: 'The control panel on my Whirlpool dishwasher stopped responding' },
  ],
}

const FILTERS: { label: string; value: ApplianceFilter }[] = [
  { label: 'All',          value: 'all' },
  { label: 'Refrigerator', value: 'refrigerator' },
  { label: 'Dishwasher',   value: 'dishwasher' },
]

interface Props {
  onSelect:       (query: string) => void
  filter:         ApplianceFilter
  onFilterChange: (f: ApplianceFilter) => void
}

function WelcomeScreen({ onSelect, filter, onFilterChange }: Props) {
  const queries = QUERIES_BY_FILTER[filter]

  return (
    <div className="max-w-xl mx-auto px-4 py-12 animate-fade-in">

      {/* Greeting */}
      <div className="mb-10 text-center">
        <div className="w-12 h-12 rounded-2xl bg-brand-orange flex items-center justify-center mx-auto mb-5">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
        </div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          PartSelect Assistant
        </h1>
        <p className="text-gray-500 text-sm leading-relaxed max-w-sm mx-auto">
          Find the right part, check model compatibility, and get repair guidance for your refrigerator or dishwasher.
        </p>
      </div>

      {/* Filter tabs */}
      <div className="mb-6 flex items-center border-b border-gray-200">
        {FILTERS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => onFilterChange(value)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              filter === value
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Suggestion prompts */}
      <div className="mb-10 grid grid-cols-1 sm:grid-cols-2 gap-2">
        {queries.map(({ label, query }) => (
          <button
            key={label}
            onClick={() => onSelect(query)}
            className="text-left px-4 py-3 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 hover:border-gray-300 transition-all text-sm text-gray-700 font-medium"
          >
            {label}
            <p className="text-xs text-gray-400 mt-0.5 font-normal line-clamp-1">{query}</p>
          </button>
        ))}
      </div>

      {/* Capabilities */}
      <div className="border border-gray-200 rounded-xl p-5">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Capabilities</p>
        <ul className="space-y-3">
          {CAPABILITIES.map(({ Icon, text }) => (
            <li key={text} className="flex items-center gap-3 text-sm text-gray-600">
              <Icon className="w-4 h-4 text-gray-400 shrink-0" />
              {text}
            </li>
          ))}
        </ul>
      </div>

    </div>
  )
}

export default memo(WelcomeScreen)
