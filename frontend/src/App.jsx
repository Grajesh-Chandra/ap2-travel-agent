import React, { useState, useEffect } from 'react'
import { Plane, Shield, Search, Rocket } from 'lucide-react'
import TravelPlanner from './components/TravelPlanner'
import CheckoutFlow from './components/CheckoutFlow'
import AP2Debugger from './components/AP2Debugger'

function App() {
  const [activeTab, setActiveTab] = useState('planner')
  const [sessionData, setSessionData] = useState(null)
  const [selectedPackage, setSelectedPackage] = useState(null)

  const handleProceedToCheckout = (session, pkg) => {
    setSessionData(session)
    setSelectedPackage(pkg)
    setActiveTab('checkout')
  }

  const handleCheckoutComplete = (confirmation) => {
    // Handle successful checkout
    console.log('Checkout complete:', confirmation)
  }

  const tabs = [
    { id: 'planner', label: 'Travel Planner', icon: Plane },
    { id: 'checkout', label: 'AP2 Audit Trail', icon: Shield },
    { id: 'debugger', label: 'Protocol Debugger', icon: Search },
  ]

  return (
    <div className="min-h-screen bg-space-bg">
      {/* Header */}
      <header className="border-b border-white/[0.08] bg-panel/90 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-xl gradient-gold flex items-center justify-center shadow-lg shadow-gold/20">
                  <Rocket className="w-7 h-7 text-space-bg" />
                </div>
                <div className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-emerald-500 border-2 border-panel flex items-center justify-center">
                  <span className="text-[8px]">✓</span>
                </div>
              </div>
              <div>
                <h1 className="font-heading font-bold text-xl text-white tracking-tight">
                  Voyager AI
                </h1>
                <p className="text-xs text-gray-500 font-medium">AP2 Travel Agent Demo</p>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="flex gap-1.5 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2.5 px-5 py-2.5 rounded-lg transition-all duration-300 ${
                    activeTab === tab.id
                      ? 'bg-gold/15 text-gold border border-gold/30 shadow-sm'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  <span className="font-medium text-sm">{tab.label}</span>
                </button>
              ))}
            </nav>

            {/* Status Indicator */}
            <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="status-online" />
              <div className="text-sm">
                <span className="text-gray-300 font-medium">OpenRouter</span>
                <span className="text-gray-500 ml-1.5 text-xs">LLM</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - all tabs stay mounted to preserve state */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div style={{ display: activeTab === 'planner' ? 'block' : 'none' }}>
          <TravelPlanner
            onProceedToCheckout={handleProceedToCheckout}
            onSessionUpdate={setSessionData}
            onSelectedPackage={setSelectedPackage}
          />
        </div>
        <div style={{ display: activeTab === 'checkout' ? 'block' : 'none' }}>
          <CheckoutFlow
            sessionData={sessionData}
            selectedPackage={selectedPackage}
            onComplete={handleCheckoutComplete}
          />
        </div>
        <div style={{ display: activeTab === 'debugger' ? 'block' : 'none' }}>
          <AP2Debugger />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border-light bg-panel/50 py-4 mt-8">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
          <p>
            Voyager AI — AP2 (Agent Payments Protocol) Demo •{' '}
            <a
              href="https://github.com/google-agentic-commerce/AP2"
              className="text-gold hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              AP2 Protocol
            </a>{' '}
            •{' '}
            <a
              href="https://github.com/Grajesh-Chandra/a2a-travel-agent"
              className="text-gold hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              A2A Travel Agent
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
