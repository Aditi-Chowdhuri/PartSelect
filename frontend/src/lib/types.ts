export type MessageRole = 'user' | 'assistant'

export interface Part {
  part_number: string
  name: string
  price: number
  brand: string
  category: 'refrigerator' | 'dishwasher'
  image_url: string
  description: string
  url?: string
  rating?: number
  review_count?: number
  availability?: string
  symptoms?: string[]
  install_difficulty?: string
  install_time?: string
  video_url?: string
  compatibility?: string[]
}

export interface CartItem {
  part_number: string
  name: string
  price: number
  quantity: number
  url?: string
}

export interface Message {
  id:           string
  role:         MessageRole
  content:      string
  parts?:       Part[]
  timestamp:    Date
  responseTime?: number
  isError?:     boolean
}

export type ApplianceFilter = 'all' | 'refrigerator' | 'dishwasher'
