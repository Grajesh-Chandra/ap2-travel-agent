import React, { useState, useRef, useEffect } from 'react'
import {
  Send,
  Plane,
  Building,
  MapPin,
  Users,
  Calendar,
  DollarSign,
  Loader2,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  ShoppingCart,
} from 'lucide-react'
import AgentNetwork from './AgentNetwork'

const API_BASE = ''

export default function TravelPlanner({ onProceedToCheckout }) {
  const [message, setMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [chatHistory, setChatHistory] = useState([])
  const [sessionData, setSessionData] = useState(null)
  const [selectedPackageId, setSelectedPackageId] = useState(null)
  const chatEndRef = useRef(null)

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [chatHistory, isLoading])

  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!message.trim() || isLoading) return

    const userMessage = message.trim()
    setMessage('')
    setIsLoading(true)

    // Add user message to chat
    setChatHistory((prev) => [
      ...prev,
      { role: 'user', content: userMessage },
    ])

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          user_id: 'demo_user',
          session_id: sessionData?.session_id,
        }),
      })

      const data = await response.json()

      if (data.success) {
        // Always update session data
        setSessionData(data)

        // Add response to chat based on type
        setChatHistory((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data,
            type: data.type || 'conversation',
          },
        ])
      } else {
        setChatHistory((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.error || 'Sorry, I encountered an error.',
            type: 'error',
          },
        ])
      }
    } catch (error) {
      console.error('Chat error:', error)
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Connection error. Please check if the backend is running.',
          type: 'error',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handlePackageSelect = async (pkg) => {
    // Send a message to select this package and start checkout
    const tierMessage = pkg.tier === 'recommended'
      ? "I'll take the recommended package"
      : `I want the ${pkg.tier} package`

    setMessage(tierMessage)
    setSelectedPackageId(pkg.package_id)

    // Auto-submit the selection
    setTimeout(() => {
      document.querySelector('form')?.requestSubmit()
    }, 100)
  }

  const handleProceedToCheckout = () => {
    // Legacy: kept for compatibility, but checkout now happens through chat
    if (sessionData && selectedPackageId) {
      const pkg = sessionData.packages.find(
        (p) => p.package_id === selectedPackageId
      )
      onProceedToCheckout(sessionData, pkg)
    }
  }

  const quickPrompts = [
    'Hi, I want to plan a trip',
    'Help me book a vacation to Dubai',
    'I need a Tokyo trip for 2 people next month',
    'Find me a luxury Paris getaway',
  ]

  const tierColors = {
    value: 'border-sky-500/40 bg-gradient-to-br from-sky-500/10 to-transparent hover:border-sky-400/60',
    recommended: 'border-gold/50 bg-gradient-to-br from-gold/15 to-transparent ring-1 ring-gold/30 hover:ring-gold/50 shadow-lg shadow-gold/5',
    premium: 'border-violet-500/40 bg-gradient-to-br from-violet-500/10 to-transparent hover:border-violet-400/60',
  }

  const tierBadges = {
    value: { label: 'Smart Value', icon: '💎', color: 'text-sky-400' },
    recommended: { label: 'Best Match', icon: '⭐', color: 'text-gold' },
    premium: { label: 'Premium', icon: '👑', color: 'text-violet-400' },
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Panel - Chat */}
      <div className="lg:col-span-2 flex flex-col gap-4">
        {/* Chat History */}
        <div className="card min-h-[520px] max-h-[620px] overflow-y-auto p-6">
          {chatHistory.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 py-8">
              <div className="relative mb-6">
                <div className="w-20 h-20 rounded-2xl gradient-gold flex items-center justify-center shadow-lg shadow-gold/20">
                  <Plane className="w-10 h-10 text-space-bg" />
                </div>
                <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg">
                  <Sparkles className="w-3 h-3 text-white" />
                </div>
              </div>
              <h2 className="font-heading text-2xl font-bold text-white mb-3">
                Plan Your Dream Trip
              </h2>
              <p className="text-gray-400 mb-8 max-w-md leading-relaxed">
                Tell me about your travel plans and I'll find the perfect
                packages for you, powered by AP2 secure checkout.
              </p>

              {/* Quick Prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                {quickPrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => setMessage(prompt)}
                    className="group text-left text-sm p-4 rounded-xl bg-white/[0.03] hover:bg-white/[0.06]
                             border border-white/10 hover:border-gold/40 transition-all duration-300
                             hover:shadow-lg hover:shadow-gold/5"
                  >
                    <Sparkles className="w-4 h-4 text-gold/70 group-hover:text-gold inline mr-2 transition-colors" />
                    <span className="text-gray-300 group-hover:text-white transition-colors">{prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {chatHistory.map((msg, idx) => (
                <div
                  key={idx}
                  className={`animate-fade-in ${
                    msg.role === 'user' ? 'flex justify-end' : ''
                  }`}
                >
                  {msg.role === 'user' ? (
                    <div className="max-w-[80%] message-bubble-user shadow-lg">
                      <p className="font-medium">{msg.content}</p>
                    </div>
                  ) : msg.type === 'packages' ? (
                    <TravelResponse
                      data={msg.content}
                      selectedPackageId={selectedPackageId}
                      onSelectPackage={handlePackageSelect}
                      tierColors={tierColors}
                      tierBadges={tierBadges}
                    />
                  ) : msg.type === 'conversation' || msg.type === 'confirmation' ? (
                    <ConversationResponse
                      data={msg.content}
                      onSuggestionClick={(suggestion) => setMessage(suggestion)}
                    />
                  ) : msg.type === 'checkout_start' || msg.type === 'payment_selection' ? (
                    <CheckoutResponse
                      data={msg.content}
                      onSuggestionClick={(suggestion) => setMessage(suggestion)}
                    />
                  ) : msg.type === 'payment_complete' ? (
                    <PaymentCompleteResponse data={msg.content} />
                  ) : (
                    <div className="max-w-[80%] message-bubble-agent">
                      <p className={msg.type === 'error' ? 'text-red-400' : 'text-gray-200'}>
                        {typeof msg.content === 'string' ? msg.content : msg.content?.message || 'Processing...'}
                      </p>
                    </div>
                  )}
                </div>
              ))}

              {/* Typing indicator */}
              {isLoading && (
                <div className="animate-fade-in">
                  <div className="inline-flex items-center gap-4 px-5 py-4 rounded-2xl rounded-tl-sm bg-panel border border-white/10">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 bg-gold rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2.5 h-2.5 bg-gold/70 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2.5 h-2.5 bg-gold/40 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-gray-400 text-sm font-medium">Thinking... This may take a moment</span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSendMessage} className="flex gap-3">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Where would you like to go?"
            className="input-modern flex-1"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className="btn-gold flex items-center gap-2.5 px-7"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <Send className="w-5 h-5" />
                <span className="font-semibold">Send</span>
              </>
            )}
          </button>
        </form>

        {/* Stage indicator */}
        {sessionData?.stage && (
          <div className="flex justify-center">
            <span className="badge badge-gold text-xs">
              {sessionData.stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </span>
          </div>
        )}
      </div>

      {/* Right Panel - Agent Network */}
      <div className="lg:col-span-1">
        <AgentNetwork sessionData={sessionData} />
      </div>
    </div>
  )
}

// Conversation Response Component
function ConversationResponse({ data, onSuggestionClick }) {
  return (
    <div className="max-w-[90%]">
      <div className="glass-elevated rounded-2xl rounded-tl-sm px-5 py-5">
        {/* Message with markdown-like formatting */}
        <div className="text-gray-200 leading-relaxed mb-5">
          {data.message.split('\n').map((line, i) => {
            // Bold text between **
            const parts = line.split(/(\*\*.*?\*\*)/g)
            return (
              <p key={i} className={`${line.startsWith('-') ? 'ml-4 before:content-["•"] before:mr-2 before:text-gold' : ''} ${i > 0 ? 'mt-2' : ''}`}>
                {parts.map((part, j) =>
                  part.startsWith('**') && part.endsWith('**') ? (
                    <strong key={j} className="text-white font-semibold">
                      {part.slice(2, -2)}
                    </strong>
                  ) : (
                    <span key={j}>{part}</span>
                  )
                )}
              </p>
            )
          })}
        </div>

        {/* Suggestions */}
        {data.suggestions && data.suggestions.length > 0 && (
          <div className="space-y-2.5 pt-4 border-t border-white/10">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Quick Responses</p>
            {data.suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(suggestion)}
                className="group w-full text-left text-sm p-3.5 rounded-xl bg-white/[0.03] hover:bg-gold/10
                         border border-white/10 hover:border-gold/40 transition-all duration-300
                         flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-gold/10 flex items-center justify-center shrink-0 group-hover:bg-gold/20 transition-colors">
                  <Sparkles className="w-4 h-4 text-gold" />
                </div>
                <span className="text-gray-300 group-hover:text-white transition-colors">{suggestion}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Travel Response Component
function TravelResponse({
  data,
  selectedPackageId,
  onSelectPackage,
  tierColors,
  tierBadges,
}) {
  const { intent_mandate, packages } = data

  return (
    <div className="w-full space-y-5">
      {/* Intent Mandate Summary */}
      {intent_mandate && (
        <div className="card card-gold p-5">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-heading font-semibold text-white">
                  Intent Verified
                </h3>
                <p className="text-xs text-gray-500">AP2 Secure Mandate</p>
              </div>
            </div>
            <span className="badge badge-gold">
              AP2/v1
            </span>
          </div>
          <p className="text-gray-300 mb-4 leading-relaxed">
            {intent_mandate.natural_language_description}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.03]">
              <MapPin className="w-4 h-4 text-gold" />
              <span className="text-gray-300">
                {intent_mandate.shopping_intent?.destination || 'N/A'}
              </span>
            </div>
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.03]">
              <Users className="w-4 h-4 text-gold" />
              <span className="text-gray-300">
                {intent_mandate.shopping_intent?.travelers || 1} travelers
              </span>
            </div>
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.03]">
              <Calendar className="w-4 h-4 text-gold" />
              <span className="text-gray-300">
                {intent_mandate.shopping_intent?.travel_dates?.start || 'TBD'}
              </span>
            </div>
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/[0.03]">
              <DollarSign className="w-4 h-4 text-gold" />
              <span className="text-gray-300">
                ${intent_mandate.spending_limits?.max_total_usd?.toLocaleString() || 'N/A'}
              </span>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-white/10">
            <p className="text-xs text-gray-500 flex items-center gap-2">
              <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
              Mandate ID:{' '}
              <code className="font-mono text-gray-400 bg-white/5 px-2 py-0.5 rounded">
                {intent_mandate.mandate_id}
              </code>
            </p>
          </div>
        </div>
      )}

      {/* Travel Packages */}
      {packages && packages.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-heading text-lg font-semibold text-white">
              Available Packages
            </h3>
            <span className="text-xs text-gray-500">{packages.length} options</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {packages.map((pkg) => (
              <PackageCard
                key={pkg.package_id}
                pkg={pkg}
                isSelected={selectedPackageId === pkg.package_id}
                onSelect={onSelectPackage}
                tierColors={tierColors}
                tierBadges={tierBadges}
              />
            ))}
          </div>
          <div className="flex items-center justify-center gap-2 mt-4 py-3 px-4 rounded-xl bg-white/[0.02] border border-white/5">
            <Sparkles className="w-4 h-4 text-gold/70" />
            <p className="text-sm text-gray-400">
              Click a package or say <span className="text-gold">"I want the recommended package"</span>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// Package Card Component
function PackageCard({ pkg, isSelected, onSelect, tierColors, tierBadges }) {
  const tier = tierBadges[pkg.tier] || tierBadges.value
  const colorClass = tierColors[pkg.tier] || tierColors.value

  return (
    <div
      onClick={() => onSelect(pkg)}
      className={`card card-interactive transition-all duration-300 hover:translate-y-[-2px] ${colorClass} ${
        isSelected ? 'ring-2 ring-gold shadow-lg shadow-gold/20' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <span className={`text-sm font-semibold flex items-center gap-1.5 ${tier.color}`}>
          <span className="text-base">{tier.icon}</span>
          {tier.label}
        </span>
        {pkg.tier === 'recommended' && (
          <span className="badge badge-gold text-[10px]">
            Best Match
          </span>
        )}
      </div>

      {/* Flights */}
      {pkg.flights && pkg.flights[0] && (
        <div className="mb-3 p-3 rounded-lg bg-white/[0.03]">
          <div className="flex items-center gap-2.5 text-sm">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center">
              <Plane className="w-4 h-4 text-sky-400" />
            </div>
            <div className="flex-1">
              <span className="text-white font-medium block">
                {pkg.flights[0].airline}
              </span>
              <span className="text-xs text-gray-500">
                ${pkg.flights[0].price_per_person_usd}/person
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Hotels */}
      {pkg.hotels && pkg.hotels[0] && (
        <div className="mb-3 p-3 rounded-lg bg-white/[0.03]">
          <div className="flex items-center gap-2.5 text-sm">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <Building className="w-4 h-4 text-amber-400" />
            </div>
            <div className="flex-1">
              <span className="text-white font-medium block">
                {pkg.hotels[0].name}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-yellow-400 text-xs">
                  {'★'.repeat(pkg.hotels[0].star_rating || 4)}
                </span>
                <span className="text-xs text-gray-500">
                  ${pkg.hotels[0].price_per_night_usd}/night
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Activities */}
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
        <Sparkles className="w-3.5 h-3.5 text-gold/50" />
        {pkg.activities?.length || 0} activities included
      </div>

      {/* Total */}
      <div className="pt-4 border-t border-white/10">
        <div className="flex items-baseline justify-between">
          <span className="text-gray-400 text-sm">Total</span>
          <div className="text-right">
            <span className="text-2xl font-bold text-white">
              ${pkg.total_usd?.toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Select Button */}
      <button
        className={`w-full mt-4 py-2.5 rounded-xl font-semibold transition-all duration-300 ${
          isSelected
            ? 'bg-gold text-space-bg shadow-lg shadow-gold/20'
            : 'bg-white/[0.06] text-white hover:bg-white/10 border border-white/10'
        }`}
      >
        {isSelected ? '✓ Selected' : 'Select Package'}
      </button>
    </div>
  )
}

// Checkout Response Component
function CheckoutResponse({ data, onSuggestionClick }) {
  return (
    <div className="max-w-[95%]">
      <div className="glass-elevated rounded-2xl rounded-tl-sm p-6 border border-gold/40">
        {/* Checkout header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-12 h-12 rounded-xl bg-gold/10 flex items-center justify-center">
            <ShoppingCart className="w-6 h-6 text-gold" />
          </div>
          <div>
            <span className="text-gold font-semibold text-lg block">Secure Checkout</span>
            <span className="text-xs text-gray-500">AP2 Protected Transaction</span>
          </div>
        </div>

        {/* Message */}
        <div className="text-gray-200 leading-relaxed mb-5">
          {data.message?.split('\n').map((line, i) => {
            const parts = line.split(/(\*\*.*?\*\*)/g)
            return (
              <p key={i} className={`${line.startsWith('-') ? 'ml-4 before:content-["•"] before:mr-2 before:text-gold' : ''} ${i > 0 ? 'mt-2' : ''}`}>
                {parts.map((part, j) =>
                  part.startsWith('**') && part.endsWith('**') ? (
                    <strong key={j} className="text-white font-semibold">
                      {part.slice(2, -2)}
                    </strong>
                  ) : (
                    <span key={j}>{part}</span>
                  )
                )}
              </p>
            )
          })}
        </div>

        {/* Selected Package Summary */}
        {data.selected_package && (
          <div className="bg-gradient-to-br from-gold/10 to-transparent rounded-xl p-4 mb-5 border border-gold/20">
            <div className="flex justify-between items-center">
              <span className="text-gray-400 text-sm">Selected Package</span>
              <span className="badge badge-gold">{data.selected_package.tier?.charAt(0).toUpperCase() + data.selected_package.tier?.slice(1)}</span>
            </div>
            <div className="flex justify-between items-baseline mt-3">
              <span className="text-gray-400">Total Amount</span>
              <span className="text-gold text-2xl font-bold">${data.selected_package.total_usd?.toLocaleString()}</span>
            </div>
          </div>
        )}

        {/* Payment Methods */}
        {data.payment_methods && data.payment_methods.length > 0 && (
          <div className="space-y-3 mb-5">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Select Payment Method</p>
            {data.payment_methods.map((pm, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(`Pay with ${pm.network} ****${pm.last4}`)}
                className="group w-full text-left p-4 rounded-xl bg-white/[0.03] hover:bg-gold/10
                         border border-white/10 hover:border-gold/40 transition-all duration-300
                         flex items-center justify-between shadow-sm hover:shadow-md"
              >
                <div className="flex items-center gap-4">
                  <div className="w-14 h-9 bg-gradient-to-br from-white/10 to-white/5 rounded-lg flex items-center justify-center text-xs font-bold text-white border border-white/10">
                    {pm.network?.toUpperCase().slice(0, 4)}
                  </div>
                  <div>
                    <span className="text-white font-medium block">•••• •••• •••• {pm.last4}</span>
                    <span className="text-xs text-gray-500">{pm.network}</span>
                  </div>
                </div>
                <div className="w-8 h-8 rounded-lg bg-white/5 group-hover:bg-gold/20 flex items-center justify-center transition-colors">
                  <ArrowRight className="w-4 h-4 text-gray-500 group-hover:text-gold transition-colors" />
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Suggestions */}
        {data.suggestions && data.suggestions.length > 0 && !data.payment_methods && (
          <div className="space-y-2.5 pt-4 border-t border-white/10">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Options</p>
            {data.suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(suggestion)}
                className="group w-full text-left text-sm p-3.5 rounded-xl bg-white/[0.03] hover:bg-gold/10
                         border border-white/10 hover:border-gold/40 transition-all duration-300
                         flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-lg bg-gold/10 flex items-center justify-center shrink-0 group-hover:bg-gold/20 transition-colors">
                  <Sparkles className="w-4 h-4 text-gold" />
                </div>
                <span className="text-gray-300 group-hover:text-white transition-colors">{suggestion}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Payment Complete Response Component
function PaymentCompleteResponse({ data }) {
  return (
    <div className="max-w-[95%]">
      <div className="relative overflow-hidden bg-gradient-to-br from-emerald-500/20 via-emerald-500/10 to-gold/10 rounded-2xl rounded-tl-sm p-8 border border-emerald-500/40">
        {/* Decorative background */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-gold/10 rounded-full blur-2xl"></div>

        {/* Success Icon */}
        <div className="relative flex items-center justify-center mb-6">
          <div className="w-20 h-20 rounded-2xl bg-emerald-500/20 flex items-center justify-center shadow-lg shadow-emerald-500/10">
            <CheckCircle2 className="w-12 h-12 text-emerald-400" />
          </div>
        </div>

        {/* Message */}
        <div className="relative text-center mb-8">
          <h3 className="text-2xl font-bold text-white mb-3">Booking Confirmed!</h3>
          <p className="text-gray-300 leading-relaxed max-w-md mx-auto">
            {data.message?.split('\n').map((line, i) => {
              if (line.includes('`')) {
                // Handle code/monospace text
                const parts = line.split(/(`[^`]+`)/g)
                return (
                  <span key={i} className="block mt-2">
                    {parts.map((part, j) =>
                      part.startsWith('`') && part.endsWith('`') ? (
                        <code key={j} className="text-xs bg-white/10 px-2 py-1 rounded-md text-gold font-mono">
                          {part.slice(1, -1)}
                        </code>
                      ) : part.startsWith('**') && part.endsWith('**') ? (
                        <strong key={j} className="text-white font-semibold">{part.slice(2, -2)}</strong>
                      ) : (
                        <span key={j}>{part}</span>
                      )
                    )}
                  </span>
                )
              }
              const parts = line.split(/(\*\*.*?\*\*)/g)
              return (
                <span key={i} className="block mt-2">
                  {parts.map((part, j) =>
                    part.startsWith('**') && part.endsWith('**') ? (
                      <strong key={j} className="text-white font-semibold">{part.slice(2, -2)}</strong>
                    ) : (
                      <span key={j}>{part}</span>
                    )
                  )}
                </span>
              )
            })}
          </p>
        </div>

        {/* Confirmation Details */}
        {data.confirmation && (
          <div className="relative bg-black/40 rounded-xl p-6 text-center border border-white/10">
            <p className="text-gray-400 text-sm font-medium uppercase tracking-wider">Confirmation Number</p>
            <p className="text-3xl font-mono font-bold text-gold mt-2 tracking-wider">
              {data.confirmation.confirmation_number}
            </p>
            <div className="mt-4 pt-4 border-t border-white/10">
              <p className="text-emerald-400 font-semibold text-lg">
                ${data.confirmation.amount_charged?.toLocaleString(undefined, {minimumFractionDigits: 2})} charged
              </p>
            </div>
          </div>
        )}

        {/* AP2 Badge */}
        <div className="relative mt-6 flex items-center justify-center">
          <span className="badge badge-success text-sm px-4 py-2">
            ✓ Secured by AP2 Verifiable Payment
          </span>
        </div>
      </div>
    </div>
  )
}
