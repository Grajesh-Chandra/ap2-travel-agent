import React, { useState, useEffect, useRef } from 'react'
import {
  MessageSquare,
  Clock,
  Brain,
  CreditCard,
  Server,
  RefreshCw,
  Trash2,
  Download,
  ChevronRight,
  Circle,
  CheckCircle2,
  AlertCircle,
  Filter,
} from 'lucide-react'

const TABS = [
  { id: 'messages', label: 'A2A Message Bus', icon: MessageSquare },
  { id: 'timeline', label: 'Mandate Timeline', icon: Clock },
  { id: 'llm', label: 'Ollama LLM Calls', icon: Brain },
  { id: 'cards', label: 'Agent Cards', icon: CreditCard },
  { id: 'logs', label: 'Server Logs', icon: Server },
]

export default function AP2Debugger() {
  const [activeTab, setActiveTab] = useState('messages')
  const [messages, setMessages] = useState([])
  const [logs, setLogs] = useState([])
  const [agentCards, setAgentCards] = useState([])
  const [isConnected, setIsConnected] = useState(false)

  // Fetch agent cards on mount
  useEffect(() => {
    fetchAgentCards()
  }, [])

  // Connect to log stream
  useEffect(() => {
    let eventSource = null

    const connectToLogs = () => {
      eventSource = new EventSource('/api/logs/stream')

      eventSource.onopen = () => {
        setIsConnected(true)
      }

      eventSource.onmessage = (event) => {
        try {
          const log = JSON.parse(event.data)
          setLogs((prev) => [...prev.slice(-499), log])

          // Extract A2A messages - look for various A2A-related patterns
          const originalMsg = log.message || ''
          const msg = originalMsg.toLowerCase()
          
          // Check for A2A message patterns
          const isA2ASent = originalMsg.includes('A2A SENT:')
          const isA2AReceived = originalMsg.includes('A2A RECEIVED:')
          
          if (isA2ASent || isA2AReceived) {
            // Parse the message format: "A2A SENT: from_agent → to_agent [method]"
            // or "A2A RECEIVED: from_agent → to_agent [method]"
            
            let direction, fromAgent, toAgent, method
            
            // Extract method from brackets [method]
            const methodMatch = originalMsg.match(/\[([^\]]+)\]/)
            method = methodMatch ? methodMatch[1] : 'message'
            
            // Parse agents from the arrow format: "from_agent → to_agent"
            const arrowMatch = originalMsg.match(/([\w_]+)\s*→\s*([\w_]+)/)
            
            if (arrowMatch) {
              const parsedFrom = arrowMatch[1]
              const parsedTo = arrowMatch[2]
              
              if (isA2ASent) {
                // SENT: shopping_agent is sending TO another agent
                direction = 'outgoing'
                fromAgent = log.agent || parsedFrom
                toAgent = parsedTo.replace('_agent', '')
              } else {
                // RECEIVED: shopping_agent is receiving FROM another agent
                direction = 'incoming'
                fromAgent = parsedFrom.replace('_agent', '')
                toAgent = log.agent || parsedTo
              }
            } else {
              // Fallback parsing
              direction = isA2ASent ? 'outgoing' : 'incoming'
              fromAgent = log.agent || 'shopping'
              toAgent = 'unknown'
            }

            // Get payload from extra fields if available
            const payload = log.extra || {}

            setMessages((prev) => [
              ...prev.slice(-99),
              {
                id: Date.now() + Math.random(),
                timestamp: log.timestamp,
                direction,
                method,
                from: fromAgent,
                to: toAgent,
                payload,
                status: 'success',
                rawMessage: originalMsg,
              },
            ])
          }
        } catch (e) {
          console.error('Failed to parse log:', e)
        }
      }

      eventSource.onerror = () => {
        setIsConnected(false)
        eventSource.close()
        // Reconnect after 3 seconds
        setTimeout(connectToLogs, 3000)
      }
    }

    connectToLogs()

    return () => {
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [])

  const fetchAgentCards = async () => {
    const agents = [
      { name: 'Shopping Agent', port: 8000 },
      { name: 'Merchant Agent', port: 8001 },
      { name: 'Credentials Agent', port: 8002 },
      { name: 'Payment Agent', port: 8003 },
    ]

    const cards = await Promise.all(
      agents.map(async (agent) => {
        try {
          const res = await fetch(`http://localhost:${agent.port}/.well-known/agent.json`)
          if (res.ok) {
            return { ...agent, card: await res.json(), status: 'online' }
          }
        } catch (e) {
          return { ...agent, card: null, status: 'offline' }
        }
        return { ...agent, card: null, status: 'offline' }
      })
    )

    setAgentCards(cards)
  }

  const clearLogs = () => {
    setLogs([])
    setMessages([])
  }

  const downloadLogs = () => {
    const blob = new Blob([JSON.stringify(logs, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ap2-logs-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border-light px-4 bg-panel-secondary">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'text-gold border-gold'
                : 'text-gray-400 border-transparent hover:text-white'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}

        <div className="flex-1" />

        {/* Connection status */}
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-success animate-pulse' : 'bg-red-500'
            }`}
          />
          <span className="text-gray-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        {/* Actions */}
        <button
          onClick={() => fetchAgentCards()}
          className="p-2 text-gray-400 hover:text-white"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
        <button
          onClick={clearLogs}
          className="p-2 text-gray-400 hover:text-white"
          title="Clear"
        >
          <Trash2 className="w-4 h-4" />
        </button>
        <button
          onClick={downloadLogs}
          className="p-2 text-gray-400 hover:text-white"
          title="Download"
        >
          <Download className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'messages' && <MessageBusView messages={messages} />}
        {activeTab === 'timeline' && <MandateTimelineView logs={logs} />}
        {activeTab === 'llm' && <LLMCallsView logs={logs} />}
        {activeTab === 'cards' && <AgentCardsView cards={agentCards} />}
        {activeTab === 'logs' && <ServerLogsView logs={logs} />}
      </div>
    </div>
  )
}

// A2A Message Bus View
function MessageBusView({ messages }) {
  const [filter, setFilter] = useState('all')
  const [expanded, setExpanded] = useState(null)

  const filteredMessages = messages.filter((msg) => {
    if (filter === 'all') return true
    const content = `${msg.method || ''} ${msg.message || ''}`.toLowerCase()
    if (filter === 'intent') return content.includes('intent')
    if (filter === 'cart') return content.includes('cart') || content.includes('package')
    if (filter === 'payment') return content.includes('payment')
    if (filter === 'token') return content.includes('token') || content.includes('vdc')
    return content.includes(filter)
  })

  return (
    <div className="flex flex-col h-full">
      {/* Filter */}
      <div className="p-4 border-b border-border-light flex items-center gap-2">
        <Filter className="w-4 h-4 text-gray-400" />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-panel-secondary text-white text-sm rounded px-3 py-1.5 border border-border-light"
        >
          <option value="all">All Messages</option>
          <option value="intent">Intent Mandate</option>
          <option value="cart">Cart Mandate</option>
          <option value="payment">Payment Mandate</option>
          <option value="token">Tokenization</option>
        </select>
        <span className="text-gray-400 text-sm ml-2">
          {filteredMessages.length} messages
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-2">
        {filteredMessages.length === 0 ? (
          <div className="text-center text-gray-500 py-12">
            No A2A messages yet. Start a conversation to see the protocol in action.
          </div>
        ) : (
          filteredMessages.map((msg) => (
            <div
              key={msg.id}
              className={`rounded-lg border overflow-hidden ${
                msg.status === 'error'
                  ? 'border-red-500/30 bg-red-500/5'
                  : 'border-border-light bg-panel-secondary/50'
              }`}
            >
              <button
                onClick={() => setExpanded(expanded === msg.id ? null : msg.id)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left"
              >
                <ChevronRight
                  className={`w-4 h-4 text-gray-400 transition-transform ${
                    expanded === msg.id ? 'rotate-90' : ''
                  }`}
                />
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    msg.direction === 'incoming'
                      ? 'bg-blue-500/20 text-blue-300'
                      : 'bg-green-500/20 text-green-300'
                  }`}
                >
                  {msg.direction === 'incoming' ? '←' : '→'}
                </span>
                <span className="text-white font-medium text-sm">
                  {msg.method}
                </span>
                <span className="text-gray-400 text-xs">
                  {msg.from} → {msg.to}
                </span>
                <span className="flex-1" />
                <span className="text-gray-500 text-xs font-mono">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
                {msg.status === 'error' ? (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-success" />
                )}
              </button>

              {expanded === msg.id && (
                <div className="px-4 pb-4 border-t border-border-light pt-3">
                  <pre className="text-xs font-mono text-gray-300 bg-space-bg rounded p-3 overflow-auto max-h-64">
                    {JSON.stringify(msg.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// Mandate Timeline View
function MandateTimelineView({ logs }) {
  // Look for A2A and mandate-related events
  const relevantEvents = logs.filter(
    (log) =>
      log.message?.toLowerCase().includes('mandate') ||
      log.message?.toLowerCase().includes('a2a') ||
      log.message?.toLowerCase().includes('package') ||
      log.message?.toLowerCase().includes('payment')
  )

  // More specific checks for each stage
  const hasIntent = relevantEvents.some((e) =>
    e.message?.includes('IntentMandate') ||
    e.message?.toLowerCase().includes('intent') && e.message?.toLowerCase().includes('creat')
  )
  const hasPackages = relevantEvents.some((e) =>
    e.message?.toLowerCase().includes('package') &&
    (e.message?.toLowerCase().includes('generat') || e.message?.toLowerCase().includes('found'))
  )
  const hasCartMandate = relevantEvents.some((e) =>
    e.message?.includes('CartMandate') ||
    (e.message?.toLowerCase().includes('cart') && e.message?.toLowerCase().includes('mandate'))
  )
  const hasPayment = relevantEvents.some((e) =>
    e.message?.includes('PaymentMandate') ||
    (e.message?.toLowerCase().includes('payment') && e.message?.toLowerCase().includes('process'))
  )

  const events = [
    {
      step: 1,
      name: 'Intent Capture',
      description: 'User specifies travel preferences',
      status: hasIntent ? 'completed' : 'pending',
    },
    {
      step: 2,
      name: 'Intent Signed',
      description: 'IntentMandate created with spending limits',
      status: hasIntent ? 'completed' : 'pending',
    },
    {
      step: 3,
      name: 'Merchant Cart',
      description: 'Travel package assembled by merchant',
      status: hasPackages ? 'completed' : 'pending',
    },
    {
      step: 4,
      name: 'Cart Mandate',
      description: 'CartMandate signed by user and merchant',
      status: hasCartMandate ? 'completed' : 'pending',
    },
    {
      step: 5,
      name: 'Payment Processed',
      description: 'PaymentMandate executed with confirmation',
      status: hasPayment ? 'completed' : 'pending',
    },
  ]

  return (
    <div className="p-6">
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-6 top-8 bottom-8 w-0.5 bg-border-light" />

        <div className="space-y-8">
          {events.map((event) => (
            <div key={event.step} className="flex items-start gap-4">
              <div
                className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center ${
                  event.status === 'completed'
                    ? 'bg-success text-white'
                    : 'bg-panel-secondary border-2 border-border-light text-gray-400'
                }`}
              >
                {event.status === 'completed' ? (
                  <CheckCircle2 className="w-6 h-6" />
                ) : (
                  <span className="text-lg font-bold">{event.step}</span>
                )}
              </div>
              <div className="flex-1 pt-2">
                <h4
                  className={`font-semibold ${
                    event.status === 'completed' ? 'text-white' : 'text-gray-400'
                  }`}
                >
                  {event.name}
                </h4>
                <p className="text-sm text-gray-500">{event.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// LLM Calls View
function LLMCallsView({ logs }) {
  const llmLogs = logs.filter(
    (log) =>
      log.event_type === 'llm_call' ||
      log.message?.toLowerCase().includes('ollama') ||
      log.message?.toLowerCase().includes('llm')
  )

  return (
    <div className="p-4 space-y-4">
      {llmLogs.length === 0 ? (
        <div className="text-center text-gray-500 py-12">
          <Brain className="w-12 h-12 mx-auto mb-4 opacity-30" />
          No LLM calls recorded yet
        </div>
      ) : (
        llmLogs.map((log, idx) => (
          <div
            key={idx}
            className="bg-panel-secondary rounded-lg p-4 border border-border-light"
          >
            <div className="flex items-center gap-3 mb-3">
              <Brain className="w-5 h-5 text-gold" />
              <span className="text-white font-medium">
                Ollama / qwen3:8b
              </span>
              <span className="text-gray-500 text-xs font-mono">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              {log.duration_ms && (
                <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
                  {log.duration_ms}ms
                </span>
              )}
            </div>

            {log.prompt && (
              <div className="mb-3">
                <span className="text-xs text-gray-500 block mb-1">Prompt</span>
                <pre className="text-xs font-mono text-gray-300 bg-space-bg rounded p-3 overflow-auto max-h-32">
                  {log.prompt}
                </pre>
              </div>
            )}

            {log.response && (
              <div>
                <span className="text-xs text-gray-500 block mb-1">Response</span>
                <pre className="text-xs font-mono text-gray-300 bg-space-bg rounded p-3 overflow-auto max-h-32">
                  {typeof log.response === 'string'
                    ? log.response
                    : JSON.stringify(log.response, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

// Agent Cards View
function AgentCardsView({ cards }) {
  const [expanded, setExpanded] = useState(null)

  return (
    <div className="p-4 grid grid-cols-2 gap-4">
      {cards.map((agent) => (
        <div
          key={agent.port}
          className={`rounded-lg border overflow-hidden ${
            agent.status === 'online'
              ? 'border-success/30 bg-success/5'
              : 'border-red-500/30 bg-red-500/5'
          }`}
        >
          <div className="p-4">
            <div className="flex items-center gap-3 mb-3">
              <div
                className={`w-3 h-3 rounded-full ${
                  agent.status === 'online'
                    ? 'bg-success animate-pulse'
                    : 'bg-red-500'
                }`}
              />
              <span className="text-white font-semibold">{agent.name}</span>
              <span className="text-gray-500 text-xs font-mono">
                :{agent.port}
              </span>
            </div>

            {agent.card ? (
              <>
                <div className="text-sm text-gray-400 mb-2">
                  {agent.card.description}
                </div>
                <div className="flex flex-wrap gap-2 mb-2">
                  {/* Skills */}
                  {Array.isArray(agent.card.skills) && agent.card.skills.map((skill, idx) => (
                    <span
                      key={idx}
                      className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded"
                    >
                      {skill.name || skill.id}
                    </span>
                  ))}
                </div>
                {/* Capabilities Extensions */}
                {agent.card.capabilities?.extensions && (
                  <div className="flex flex-wrap gap-2">
                    {agent.card.capabilities.extensions.map((ext, idx) => (
                      <span
                        key={idx}
                        className="text-xs bg-gold/20 text-gold px-2 py-0.5 rounded"
                      >
                        {ext.uri?.split('/').pop() || 'AP2'}
                      </span>
                    ))}
                  </div>
                )}

                <button
                  onClick={() =>
                    setExpanded(expanded === agent.port ? null : agent.port)
                  }
                  className="text-xs text-gold mt-3 flex items-center gap-1"
                >
                  <ChevronRight
                    className={`w-3 h-3 transition-transform ${
                      expanded === agent.port ? 'rotate-90' : ''
                    }`}
                  />
                  {expanded === agent.port ? 'Hide' : 'Show'} full card
                </button>

                {expanded === agent.port && (
                  <pre className="text-xs font-mono text-gray-300 bg-space-bg rounded p-3 mt-3 overflow-auto max-h-64">
                    {JSON.stringify(agent.card, null, 2)}
                  </pre>
                )}
              </>
            ) : (
              <div className="text-sm text-red-400">
                Agent unavailable - check if server is running
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// Server Logs View
function ServerLogsView({ logs }) {
  const scrollRef = useRef(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [levelFilter, setLevelFilter] = useState('all')

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const filteredLogs = logs.filter((log) => {
    if (levelFilter === 'all') return true
    return log.level === levelFilter
  })

  const getLevelColor = (level) => {
    switch (level) {
      case 'DEBUG':
        return 'text-gray-400'
      case 'INFO':
        return 'text-blue-400'
      case 'WARNING':
        return 'text-yellow-400'
      case 'ERROR':
        return 'text-red-400'
      default:
        return 'text-gray-400'
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filters */}
      <div className="p-4 border-b border-border-light flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            className="bg-panel-secondary text-white text-sm rounded px-3 py-1.5 border border-border-light"
          >
            <option value="all">All Levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-border-light"
          />
          Auto-scroll
        </label>
        <span className="text-gray-500 text-sm">{logs.length} entries</span>
      </div>

      {/* Logs */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-auto p-4 bg-space-bg font-mono text-xs"
      >
        {filteredLogs.length === 0 ? (
          <div className="text-center text-gray-500 py-12">
            Waiting for log entries...
          </div>
        ) : (
          filteredLogs.map((log, idx) => (
            <div key={idx} className="flex gap-3 py-1 hover:bg-white/5">
              <span className="text-gray-600 shrink-0">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={`shrink-0 w-16 ${getLevelColor(log.level)}`}>
                [{log.level}]
              </span>
              <span className="text-blue-400 shrink-0">
                {log.agent || 'system'}
              </span>
              <span className="text-gray-300 break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
