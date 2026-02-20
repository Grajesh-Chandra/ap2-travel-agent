import React, { useState, useEffect } from 'react'
import { RefreshCw, Circle, ArrowRight, Zap, Server, ShoppingCart, CreditCard, DollarSign, Info, X } from 'lucide-react'

const AGENTS = [
  {
    id: 'shopping',
    name: 'Shopping Agent',
    port: 8000,
    icon: ShoppingCart,
    description: 'User-facing orchestrator with LLM',
    color: 'gold',
    position: { x: 50, y: 30 },
    details: {
      role: 'Orchestrator',
      protocol: 'A2A + AP2',
      features: ['LLM-powered chat', 'Session management', 'Intent extraction', 'Multi-agent coordination'],
      endpoints: ['/api/chat', '/a2a'],
      tech: 'FastAPI + OpenRouter LLM'
    }
  },
  {
    id: 'merchant',
    name: 'Merchant Agent',
    port: 8001,
    icon: Server,
    description: 'Catalog search & package generation',
    color: 'blue',
    position: { x: 20, y: 70 },
    details: {
      role: 'Catalog Provider',
      protocol: 'A2A',
      features: ['Travel package search', 'IntentMandate validation', 'CartMandate creation', 'Price calculation'],
      endpoints: ['/a2a', '/health'],
      tech: 'FastAPI + Mock Catalog'
    }
  },
  {
    id: 'credentials',
    name: 'Credentials Agent',
    port: 8002,
    icon: CreditCard,
    description: 'Payment method tokenization',
    color: 'purple',
    position: { x: 50, y: 70 },
    details: {
      role: 'Tokenization Service',
      protocol: 'A2A + AP2',
      features: ['Card tokenization', 'Secure storage', 'PCI compliance', 'Token retrieval'],
      endpoints: ['/a2a', '/health'],
      tech: 'FastAPI + Secure Vault'
    }
  },
  {
    id: 'payment',
    name: 'Payment Agent',
    port: 8003,
    icon: DollarSign,
    description: 'Payment processing & settlement',
    color: 'green',
    position: { x: 80, y: 70 },
    details: {
      role: 'Payment Processor',
      protocol: 'A2A + AP2',
      features: ['PaymentMandate execution', 'VDC verification', 'Transaction settlement', 'Confirmation generation'],
      endpoints: ['/a2a', '/health'],
      tech: 'FastAPI + Mock Gateway'
    }
  },
]

const CONNECTIONS = [
  { from: 'shopping', to: 'merchant', label: 'IntentMandate' },
  { from: 'shopping', to: 'credentials', label: 'Tokenize' },
  { from: 'shopping', to: 'payment', label: 'PaymentMandate' },
  { from: 'merchant', to: 'shopping', label: 'CartMandate' },
]

export default function AgentNetwork() {
  const [agentStatus, setAgentStatus] = useState({})
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [activeConnection, setActiveConnection] = useState(null)
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [hoveredAgent, setHoveredAgent] = useState(null)

  useEffect(() => {
    checkAgentStatus()
    const interval = setInterval(checkAgentStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  const checkAgentStatus = async () => {
    setIsRefreshing(true)
    const status = {}

    await Promise.all(
      AGENTS.map(async (agent) => {
        try {
          const start = Date.now()
          const res = await fetch(`http://localhost:${agent.port}/health`, {
            signal: AbortSignal.timeout(2000),
          })
          const latency = Date.now() - start
          if (res.ok) {
            const data = await res.json()
            status[agent.id] = {
              online: true,
              latency,
              sessions: data.active_sessions || 0,
              uptime: data.uptime || 'N/A',
            }
          } else {
            status[agent.id] = { online: false }
          }
        } catch (e) {
          status[agent.id] = { online: false }
        }
      })
    )

    setAgentStatus(status)
    setIsRefreshing(false)
  }

  const getColorClass = (color) => {
    switch (color) {
      case 'gold':
        return 'bg-gold/15 border-gold/50 text-gold'
      case 'blue':
        return 'bg-sky-500/15 border-sky-500/50 text-sky-400'
      case 'purple':
        return 'bg-violet-500/15 border-violet-500/50 text-violet-400'
      case 'green':
        return 'bg-emerald-500/15 border-emerald-500/50 text-emerald-400'
      default:
        return 'bg-gray-500/15 border-gray-500/50 text-gray-400'
    }
  }

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Zap className="w-5 h-5 text-gold" />
            Agent Network
          </h2>
          <p className="text-xs text-gray-500 mt-1">Live A2A mesh status</p>
        </div>
        <button
          onClick={checkAgentStatus}
          disabled={isRefreshing}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/10
            text-gray-300 hover:bg-white/[0.06] hover:border-white/20 transition-all text-sm ${
              isRefreshing ? 'opacity-50' : ''
            }`}
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* Network Visualization */}
      <div className="relative bg-space-bg/50 rounded-xl border border-white/10 p-6 mb-5" style={{ height: 320 }}>
        {/* Connection Lines */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#FFD700" />
            </marker>
          </defs>
          {CONNECTIONS.map((conn, idx) => {
            const fromAgent = AGENTS.find((a) => a.id === conn.from)
            const toAgent = AGENTS.find((a) => a.id === conn.to)
            const isActive = activeConnection === idx

            // Calculate positions
            const x1 = `${fromAgent.position.x}%`
            const y1 = `${fromAgent.position.y}%`
            const x2 = `${toAgent.position.x}%`
            const y2 = `${toAgent.position.y}%`

            return (
              <g key={idx}>
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={isActive ? '#FFD700' : '#374151'}
                  strokeWidth={isActive ? 3 : 2}
                  strokeDasharray={isActive ? '0' : '5,5'}
                  markerEnd="url(#arrowhead)"
                  className="transition-all duration-300"
                />
              </g>
            )
          })}
        </svg>

        {/* Agent Nodes */}
        {AGENTS.map((agent) => {
          const status = agentStatus[agent.id]
          const isOnline = status?.online
          const isSelected = selectedAgent === agent.id

          return (
            <div
              key={agent.id}
              className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-300"
              style={{
                left: `${agent.position.x}%`,
                top: `${agent.position.y}%`,
              }}
            >
              <button
                onClick={() => setSelectedAgent(isSelected ? null : agent.id)}
                className={`relative group ${isSelected ? 'scale-110' : ''}`}
              >
                {/* Pulse animation for online */}
                {isOnline && (
                  <div className={`absolute inset-0 rounded-full animate-ping opacity-20 ${
                    agent.color === 'gold' ? 'bg-gold' :
                    agent.color === 'blue' ? 'bg-blue-500' :
                    agent.color === 'purple' ? 'bg-purple-500' :
                    'bg-success'
                  }`} />
                )}

                {/* Main circle */}
                <div
                  className={`relative w-20 h-20 rounded-full border-2 flex items-center justify-center
                    ${isOnline ? getColorClass(agent.color) : 'bg-red-500/20 border-red-500/50 text-red-400'}
                    ${isSelected ? 'ring-4 ring-white/20' : ''}
                    transition-all duration-300 cursor-pointer hover:scale-105`}
                >
                  <agent.icon className="w-8 h-8" />
                </div>

                {/* Status indicator */}
                <div
                  className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-space-bg
                    ${isOnline ? 'bg-success' : 'bg-red-500'}`}
                />

                {/* Label */}
                <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 whitespace-nowrap">
                  <span className="text-xs text-white font-medium">{agent.name}</span>
                </div>
              </button>
            </div>
          )
        })}

        {/* Connection Labels */}
        {CONNECTIONS.map((conn, idx) => {
          const fromAgent = AGENTS.find((a) => a.id === conn.from)
          const toAgent = AGENTS.find((a) => a.id === conn.to)

          // Midpoint
          const midX = (fromAgent.position.x + toAgent.position.x) / 2
          const midY = (fromAgent.position.y + toAgent.position.y) / 2

          return (
            <div
              key={idx}
              className="absolute transform -translate-x-1/2 -translate-y-1/2 pointer-events-none"
              style={{
                left: `${midX}%`,
                top: `${midY}%`,
              }}
            >
              <span className="text-xs text-gray-500 bg-space-bg px-2 py-0.5 rounded">
                {conn.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Agent Details Grid */}
      <div className="grid grid-cols-2 gap-3 relative">
        {AGENTS.map((agent) => {
          const status = agentStatus[agent.id]
          const isOnline = status?.online
          const isSelected = selectedAgent === agent.id
          const isHovered = hoveredAgent === agent.id

          return (
            <div
              key={agent.id}
              onClick={() => setSelectedAgent(isSelected ? null : agent.id)}
              onMouseEnter={() => setHoveredAgent(agent.id)}
              onMouseLeave={() => setHoveredAgent(null)}
              className={`relative rounded-xl border p-3.5 cursor-pointer transition-all duration-300 ${
                isSelected
                  ? 'border-gold/50 bg-gold/10 shadow-lg shadow-gold/5'
                  : isOnline
                  ? 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
                  : 'border-red-500/30 bg-red-500/5'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center ${getColorClass(
                    agent.color
                  )}`}
                >
                  <agent.icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-semibold text-white truncate">
                    {agent.name.replace(' Agent', '')}
                  </h4>
                  <span className="text-[10px] text-gray-500 font-mono">
                    :{agent.port}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Info className="w-3 h-3 text-gray-500" />
                  <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-red-500'}`} />
                </div>
              </div>

              {isOnline && (
                <div className="flex gap-3 text-[10px] mt-2 pt-2 border-t border-white/5">
                  <div>
                    <span className="text-gray-500">Latency</span>
                    <span className="text-emerald-400 font-mono ml-1.5">
                      {status.latency}ms
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Sessions</span>
                    <span className="text-white font-mono ml-1.5">{status.sessions}</span>
                  </div>
                </div>
              )}

              {/* Hover Details Popup */}
              {isHovered && (
                <div className="absolute z-50 left-0 right-0 top-full mt-2 p-4 rounded-xl border border-white/20 bg-panel shadow-2xl shadow-black/50 animate-fade-in">
                  <div className="flex items-center justify-between mb-3">
                    <h5 className="text-sm font-semibold text-white flex items-center gap-2">
                      <agent.icon className={`w-4 h-4 ${getColorClass(agent.color).split(' ').pop()}`} />
                      {agent.name}
                    </h5>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      isOnline ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {isOnline ? 'ONLINE' : 'OFFLINE'}
                    </span>
                  </div>

                  <p className="text-xs text-gray-400 mb-3">{agent.description}</p>

                  <div className="space-y-2.5 text-[11px]">
                    <div className="flex items-start gap-2">
                      <span className="text-gray-500 w-16 shrink-0">Role</span>
                      <span className="text-white font-medium">{agent.details.role}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-gray-500 w-16 shrink-0">Protocol</span>
                      <span className="text-gold font-mono text-[10px]">{agent.details.protocol}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-gray-500 w-16 shrink-0">Tech</span>
                      <span className="text-gray-300">{agent.details.tech}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-gray-500 w-16 shrink-0">Endpoints</span>
                      <div className="flex flex-wrap gap-1">
                        {agent.details.endpoints.map((ep, i) => (
                          <code key={i} className="text-[9px] bg-white/10 px-1.5 py-0.5 rounded text-sky-400">
                            {ep}
                          </code>
                        ))}
                      </div>
                    </div>
                    <div className="pt-2 border-t border-white/5">
                      <span className="text-gray-500 text-[10px] block mb-1.5">Features</span>
                      <div className="flex flex-wrap gap-1">
                        {agent.details.features.map((feat, i) => (
                          <span key={i} className="text-[9px] bg-white/5 px-2 py-1 rounded-full text-gray-300">
                            {feat}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="mt-5 pt-4 border-t border-white/5 flex items-center justify-center gap-5 text-[10px] text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span>Online</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
          <span>Offline</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-5 h-0.5 bg-gold" />
          <span>Active</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Info className="w-3 h-3" />
          <span>Hover for details</span>
        </div>
      </div>
    </div>
  )
}
