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
  Shield,
  CreditCard,
  FileCheck,
  RotateCcw,
  Star,
} from 'lucide-react'
import AgentNetwork from './AgentNetwork'

const API_BASE = ''

export default function TravelPlanner({
  onProceedToCheckout,
  onSessionUpdate,
  onSelectedPackage,
}) {
  const [message, setMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [chatHistory, setChatHistory] = useState([])
  const [sessionData, setSessionData] = useState(null)
  const [selectedPackageId, setSelectedPackageId] = useState(null)
  const chatEndRef = useRef(null)

  const handleResetSession = async () => {
    try {
      await fetch(`${API_BASE}/api/reset-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionData?.session_id }),
      })
    } catch (e) {
      // ignore
    }
    setChatHistory([])
    setSessionData(null)
    setSelectedPackageId(null)
    setMessage('')
    onSessionUpdate?.(null)
    onSelectedPackage?.(null)
  }

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
        onSessionUpdate?.(data)

        if (data.selected_package) {
          onSelectedPackage?.(data.selected_package)
        }

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

  const sendSuggestion = (text) => {
    setMessage(text)
    setTimeout(() => {
      document.querySelector('form')?.requestSubmit()
    }, 100)
  }

  const handleProceedToCheckout = () => {
    if (sessionData && selectedPackageId) {
      const pkg = sessionData.packages?.find(
        (p) => p.package_id === selectedPackageId
      ) || sessionData.selected_package
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
                    onClick={() => sendSuggestion(prompt)}
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
                    <div className="max-w-[80%] message-bubble-user shadow-lg shadow-gold/10">
                      <p className="font-medium text-sm leading-relaxed">{msg.content}</p>
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
                      onSuggestionClick={sendSuggestion}
                    />
                  ) : msg.type === 'checkout_start' || msg.type === 'payment_selection' ? (
                    <CheckoutResponse
                      data={msg.content}
                      onSuggestionClick={sendSuggestion}
                    />
                  ) : msg.type === 'payment_complete' ? (
                    <PaymentCompleteResponse
                      data={msg.content}
                      onSuggestionClick={sendSuggestion}
                    />
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

        {/* Stage indicator + Reset */}
        <div className="flex items-center justify-center gap-3">
          {sessionData?.stage && (
            <span className="badge badge-gold text-xs">
              {sessionData.stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </span>
          )}
          {sessionData && (
            <button
              onClick={handleResetSession}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       text-gray-400 hover:text-white bg-white/[0.03] hover:bg-red-500/15
                       border border-white/10 hover:border-red-500/40 transition-all duration-300"
              title="Reset session and start fresh"
            >
              <RotateCcw className="w-3 h-3" />
              Reset Session
            </button>
          )}
        </div>
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
        <div className="text-gray-200 leading-relaxed mb-5 whitespace-pre-wrap">
          {data.message?.split('\n').map((line, i) => {
            // Bold text between **
            const parts = line.split(/(\*\*.*?\*\*)/g)
            const isEmpty = line.trim() === ''
            return (
              <p
                key={i}
                className={`${line.startsWith('-') ? 'ml-4 before:content-["•"] before:mr-2 before:text-gold' : ''} ${i > 0 && !isEmpty ? 'mt-2' : ''} ${isEmpty ? 'h-2' : ''}`}
              >
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
        <div className="text-gray-200 leading-relaxed mb-5 whitespace-pre-wrap">
          {data.message?.split('\n').map((line, i) => {
            const parts = line.split(/(\*\*.*?\*\*)/g)
            const isEmpty = line.trim() === ''
            return (
              <p
                key={i}
                className={`${line.startsWith('-') ? 'ml-4 before:content-["•"] before:mr-2 before:text-gold' : ''} ${i > 0 && !isEmpty ? 'mt-2' : ''} ${isEmpty ? 'h-2' : ''}`}
              >
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
function PaymentCompleteResponse({ data, onSuggestionClick }) {
  const pkg = data.selected_package || {}
  const mandates = data.mandates || {}
  const confirmation = data.confirmation || {}
  const flight = pkg.flights?.[0]
  const hotel = pkg.hotels?.[0]

  return (
    <div className="w-full space-y-4">
      {/* Success Header */}
      <div className="relative overflow-hidden bg-gradient-to-br from-emerald-500/20 via-emerald-500/10 to-gold/10 rounded-2xl rounded-tl-sm p-6 border border-emerald-500/40">
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-gold/10 rounded-full blur-2xl"></div>

        <div className="relative flex items-center gap-4 mb-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 flex items-center justify-center shadow-lg shadow-emerald-500/10">
            <CheckCircle2 className="w-8 h-8 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">Booking Confirmed!</h3>
            <p className="text-sm text-gray-400">Your trip is all set — AP2 secured</p>
          </div>
          <span className="ml-auto badge badge-success text-xs">✓ AP2 Verified</span>
        </div>

        {/* Confirmation Card */}
        <div className="relative bg-black/40 rounded-xl p-5 border border-white/10 mb-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Confirmation Number</p>
            <span className="text-gold text-xs font-mono">{pkg.tier?.toUpperCase() || 'STANDARD'} PACKAGE</span>
          </div>
          <p className="text-2xl font-mono font-bold text-gold tracking-wider">
            {confirmation.confirmation_number || 'N/A'}
          </p>
          <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between">
            <p className="text-emerald-400 font-semibold text-lg">
              ${confirmation.amount_charged?.toLocaleString(undefined, {minimumFractionDigits: 2}) || pkg.total_usd?.toLocaleString()}
              <span className="text-gray-500 text-sm font-normal ml-1">USD charged</span>
            </p>
            <span className="text-xs text-gray-500">via AP2 Payment Agent</span>
          </div>
        </div>

        {/* Trip Details Grid */}
        <div className="relative grid grid-cols-2 gap-3">
          {flight && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="w-9 h-9 rounded-lg bg-sky-500/10 flex items-center justify-center">
                <Plane className="w-4 h-4 text-sky-400" />
              </div>
              <div className="min-w-0">
                <p className="text-white text-sm font-medium truncate">{flight.airline}</p>
                <p className="text-xs text-gray-500">${flight.price_per_person_usd}/person</p>
              </div>
            </div>
          )}
          {hotel && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center">
                <Building className="w-4 h-4 text-amber-400" />
              </div>
              <div className="min-w-0">
                <p className="text-white text-sm font-medium truncate">{hotel.name}</p>
                <p className="text-xs text-gray-500">
                  <span className="text-yellow-400">{'★'.repeat(hotel.star_rating || 4)}</span>
                  {' '}{hotel.nights || ''} nights
                </p>
              </div>
            </div>
          )}
          {pkg.activities?.length > 0 && (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/5">
              <div className="w-9 h-9 rounded-lg bg-violet-500/10 flex items-center justify-center">
                <Star className="w-4 h-4 text-violet-400" />
              </div>
              <div>
                <p className="text-white text-sm font-medium">{pkg.activities.length} Activities</p>
                <p className="text-xs text-gray-500">Included in package</p>
              </div>
            </div>
          )}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/5">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <CreditCard className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-white text-sm font-medium">
                {confirmation.payment_method?.network || 'Card'} ••••{confirmation.payment_method?.last4 || '****'}
              </p>
              <p className="text-xs text-gray-500">Payment method</p>
            </div>
          </div>
        </div>
      </div>

      {/* AP2 Mandate Chain */}
      {mandates.intent && (
        <div className="card p-4 border border-white/10">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-gold" />
            <h4 className="text-sm font-semibold text-white">AP2 Mandate Chain</h4>
            <span className="badge badge-gold text-[10px] ml-auto">3 of 3 verified</span>
          </div>
          <div className="space-y-2">
            {/* Intent Mandate */}
            <div className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="w-7 h-7 rounded-md bg-emerald-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-emerald-400">Intent Mandate</p>
                <p className="text-[10px] text-gray-500 font-mono truncate">
                  {mandates.intent?.mandate_id || 'N/A'}
                </p>
              </div>
              <FileCheck className="w-3.5 h-3.5 text-emerald-500/50" />
            </div>
            {/* Cart Mandate */}
            <div className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="w-7 h-7 rounded-md bg-emerald-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-emerald-400">Cart Mandate</p>
                <p className="text-[10px] text-gray-500 font-mono truncate">
                  {mandates.cart?.mandate_id || 'N/A'}
                </p>
              </div>
              <FileCheck className="w-3.5 h-3.5 text-emerald-500/50" />
            </div>
            {/* Payment Mandate */}
            <div className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="w-7 h-7 rounded-md bg-emerald-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-emerald-400">Payment Mandate</p>
                <p className="text-[10px] text-gray-500 font-mono truncate">
                  {mandates.payment?.mandate_id || 'N/A'}
                </p>
              </div>
              <FileCheck className="w-3.5 h-3.5 text-emerald-500/50" />
            </div>
          </div>
        </div>
      )}

      {/* Next Journey Suggestions */}
      {data.suggestions && data.suggestions.length > 0 && onSuggestionClick && (
        <div className="glass-elevated rounded-2xl px-5 py-4">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">What's Next?</p>
          <div className="space-y-2">
            {data.suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(suggestion)}
                className="group w-full text-left text-sm p-3 rounded-xl bg-white/[0.03] hover:bg-gold/10
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
        </div>
      )}
    </div>
  )
}
