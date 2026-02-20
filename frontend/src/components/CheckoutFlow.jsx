import React, { useState, useEffect } from 'react'
import {
  Shield,
  FileText,
  ShoppingCart,
  CreditCard,
  CheckCircle2,
  Clock,
  AlertCircle,
  ChevronRight,
  Eye,
  EyeOff,
  Link2,
  ArrowRight,
  Lock,
  Fingerprint,
  Layers,
  Activity,
} from 'lucide-react'
import MandateViewer from './MandateViewer'

/**
 * AP2 Audit / Transparency View
 *
 * A read-only dashboard that shows the full AP2 mandate chain
 * and transaction audit trail after a booking completes via the
 * Travel Planner chat (delegated-access flow).
 */
export default function CheckoutFlow({ sessionData, selectedPackage, onComplete }) {
  const [expandedSection, setExpandedSection] = useState(null)

  // Derived state from sessionData
  const intentMandate = sessionData?.intent_mandate || null
  const cartMandate = sessionData?.mandates?.cart || sessionData?.cart_mandate || null
  const paymentMandate = sessionData?.mandates?.payment || sessionData?.payment_mandate || null
  const confirmation = sessionData?.confirmation || null
  const stage = sessionData?.stage || null

  const isCompleted = !!confirmation
  const hasAnyData = intentMandate || selectedPackage || cartMandate || paymentMandate || confirmation

  const toggleSection = (id) => {
    setExpandedSection(expandedSection === id ? null : id)
  }

  // ------ Awaiting State ------
  if (!hasAnyData) {
    return (
      <div className="space-y-6">
        <Header />
        <div className="card text-center py-16">
          <div className="relative inline-block mb-6">
            <div className="w-20 h-20 rounded-2xl bg-gold/10 border border-gold/20 flex items-center justify-center mx-auto">
              <Shield className="w-10 h-10 text-gold/40" />
            </div>
            <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-panel border-2 border-gold/20 flex items-center justify-center">
              <Clock className="w-3 h-3 text-gray-500" />
            </div>
          </div>
          <h3 className="font-heading text-xl font-bold text-white mb-2">
            Awaiting Booking
          </h3>
          <p className="text-gray-400 max-w-md mx-auto">
            Use the <span className="text-gold font-medium">Travel Planner</span> tab
            to plan and book a trip. The full AP2 mandate chain and audit trail will
            appear here automatically once the transaction completes.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4 max-w-lg mx-auto">
            <MiniStep icon={FileText} label="Intent Mandate" />
            <MiniStep icon={ShoppingCart} label="Cart Mandate" />
            <MiniStep icon={CreditCard} label="Payment Mandate" />
          </div>
        </div>
        <AP2ExplainerPanel />
      </div>
    )
  }

  // ------ Audit View ------
  return (
    <div className="space-y-6">
      <Header isCompleted={isCompleted} stage={stage} />

      {/* Mandate Chain Visualization */}
      <MandateChain
        intentMandate={intentMandate}
        cartMandate={cartMandate}
        paymentMandate={paymentMandate}
        isCompleted={isCompleted}
      />

      {/* Transaction Summary (when completed) */}
      {isCompleted && confirmation && (
        <TransactionSummary confirmation={confirmation} />
      )}

      {/* Selected Package */}
      {selectedPackage && (
        <CollapsibleSection
          id="package"
          title="Selected Travel Package"
          icon={ShoppingCart}
          subtitle={selectedPackage.tier ? `${selectedPackage.tier.charAt(0).toUpperCase() + selectedPackage.tier.slice(1)} Tier` : 'Package'}
          isOpen={expandedSection === 'package'}
          onToggle={() => toggleSection('package')}
        >
          <PackageSummary pkg={selectedPackage} />
        </CollapsibleSection>
      )}

      {/* Intent Mandate */}
      {intentMandate && (
        <CollapsibleSection
          id="intent"
          title="Intent Mandate"
          icon={FileText}
          subtitle={intentMandate.mandate_id}
          badge="AP2 v1"
          isOpen={expandedSection === 'intent'}
          onToggle={() => toggleSection('intent')}
          status="signed"
        >
          <MandateViewer mandate={intentMandate} type="IntentMandate" />
        </CollapsibleSection>
      )}

      {/* Cart Mandate */}
      {cartMandate && (
        <CollapsibleSection
          id="cart"
          title="Cart Mandate"
          icon={ShoppingCart}
          subtitle={cartMandate.mandate_id}
          badge="AP2 v1"
          isOpen={expandedSection === 'cart'}
          onToggle={() => toggleSection('cart')}
          status="signed"
        >
          <MandateViewer mandate={cartMandate} type="CartMandate" />
        </CollapsibleSection>
      )}

      {/* Payment Mandate */}
      {paymentMandate && (
        <CollapsibleSection
          id="payment"
          title="Payment Mandate"
          icon={CreditCard}
          subtitle={paymentMandate.mandate_id}
          badge="AP2 v1"
          isOpen={expandedSection === 'payment'}
          onToggle={() => toggleSection('payment')}
          status="signed"
        >
          <MandateViewer mandate={paymentMandate} type="PaymentMandate" />
        </CollapsibleSection>
      )}

      {/* Liability & Accountability */}
      {isCompleted && confirmation && (
        <LiabilityPanel confirmation={confirmation} />
      )}

      {/* AP2 Explainer */}
      <AP2ExplainerPanel />
    </div>
  )
}

// --- Header ---
function Header({ isCompleted, stage }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/20 flex items-center justify-center">
          <Shield className="w-5 h-5 text-gold" />
        </div>
        <div>
          <h2 className="font-heading text-xl font-bold text-white">
            AP2 Audit Trail
          </h2>
          <p className="text-sm text-gray-500">
            Mandate chain &amp; transaction transparency
          </p>
        </div>
      </div>
      {isCompleted ? (
        <span className="flex items-center gap-2 text-sm text-success bg-success/10 border border-success/20 px-4 py-2 rounded-lg">
          <CheckCircle2 className="w-4 h-4" />
          Transaction Complete
        </span>
      ) : stage ? (
        <span className="flex items-center gap-2 text-sm text-gold bg-gold/10 border border-gold/20 px-4 py-2 rounded-lg">
          <Activity className="w-4 h-4" />
          {formatStage(stage)}
        </span>
      ) : null}
    </div>
  )
}

// --- Mandate Chain Visualization ---
function MandateChain({ intentMandate, cartMandate, paymentMandate, isCompleted }) {
  const steps = [
    {
      label: 'Intent Mandate',
      icon: FileText,
      present: !!intentMandate,
      id: intentMandate?.mandate_id,
    },
    {
      label: 'Cart Mandate',
      icon: ShoppingCart,
      present: !!cartMandate,
      id: cartMandate?.mandate_id,
    },
    {
      label: 'Payment Mandate',
      icon: CreditCard,
      present: !!paymentMandate,
      id: paymentMandate?.mandate_id,
    },
    {
      label: 'Confirmed',
      icon: CheckCircle2,
      present: isCompleted,
      id: null,
    },
  ]

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-5">
        <Link2 className="w-4 h-4 text-gold" />
        <h3 className="font-heading font-semibold text-white text-sm">
          Mandate Chain
        </h3>
      </div>
      <div className="flex items-center justify-between">
        {steps.map((step, idx) => (
          <React.Fragment key={step.label}>
            <div className="flex flex-col items-center flex-1">
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all ${
                  step.present
                    ? 'bg-gold/15 border-gold text-gold'
                    : 'bg-panel-secondary border-gray-700 text-gray-600'
                }`}
              >
                <step.icon className="w-5 h-5" />
              </div>
              <span
                className={`text-xs mt-2 font-medium text-center ${
                  step.present ? 'text-gold' : 'text-gray-600'
                }`}
              >
                {step.label}
              </span>
              {step.id && (
                <span className="text-[10px] font-mono text-gray-500 mt-0.5 max-w-[100px] truncate">
                  {step.id}
                </span>
              )}
            </div>
            {idx < steps.length - 1 && (
              <div className="flex items-center pb-6">
                <ArrowRight
                  className={`w-4 h-4 ${
                    steps[idx + 1].present ? 'text-gold' : 'text-gray-700'
                  }`}
                />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

// --- Transaction Summary ---
function TransactionSummary({ confirmation }) {
  return (
    <div className="card card-success">
      <div className="flex items-center gap-3 mb-5">
        <CheckCircle2 className="w-6 h-6 text-success" />
        <h3 className="font-heading text-lg font-bold text-success">
          Booking Confirmed
        </h3>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <InfoField label="Transaction ID" value={confirmation.transaction_id} mono />
        <InfoField label="Auth Code" value={confirmation.authorization_code} mono />
        <InfoField
          label="Total Charged"
          value={
            confirmation.total_charged
              ? `$${confirmation.total_charged.toLocaleString()}`
              : confirmation.amount
              ? `$${confirmation.amount}`
              : '\u2014'
          }
          highlight
        />
        <InfoField label="Status" value={confirmation.status || 'CONFIRMED'} success />
      </div>

      {/* Booking References */}
      {confirmation.booking_references?.length > 0 && (
        <>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Booking References
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {confirmation.booking_references.map((ref, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg"
              >
                <div>
                  <span className="text-xs text-gray-400 capitalize">{ref.item_type}</span>
                  <p className="text-sm text-white">{ref.provider}</p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-gray-400">PNR</span>
                  <p className="text-gold font-mono font-bold text-sm">{ref.pnr}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// --- Liability Panel ---
function LiabilityPanel({ confirmation }) {
  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-4">
        <Lock className="w-5 h-5 text-gold" />
        <h3 className="font-heading font-semibold text-white">
          Liability &amp; Accountability
        </h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-space-bg/50 rounded-lg">
          <span className="text-xs text-gray-500 block mb-1">Transaction Mode</span>
          <div className="flex items-center gap-2">
            <Fingerprint className="w-4 h-4 text-gold" />
            <span className="text-white font-medium">Delegated Access</span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Agent signed mandates on user&apos;s behalf after OTP verification
          </p>
        </div>

        <div className="p-4 bg-space-bg/50 rounded-lg">
          <span className="text-xs text-gray-500 block mb-1">Liability Assignment</span>
          <p className="text-gold font-medium">
            {confirmation.liability_assignment || 'Merchant (standard chargeback rules)'}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            AP2 mandate chain provides complete evidence trail
          </p>
        </div>

        <div className="p-4 bg-space-bg/50 rounded-lg">
          <span className="text-xs text-gray-500 block mb-1">Audit Trail</span>
          <p className="text-white text-sm">
            {confirmation.audit_trail || 'Intent \u2192 Cart \u2192 Payment \u2192 Confirmation'}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            All mandates cryptographically linked &amp; signed
          </p>
        </div>
      </div>
    </div>
  )
}

// --- Collapsible Section ---
function CollapsibleSection({ id, title, icon: Icon, subtitle, badge, isOpen, onToggle, status, children }) {
  return (
    <div className="card overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 text-left"
      >
        <ChevronRight
          className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-90' : ''}`}
        />
        <Icon className="w-5 h-5 text-gold" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-heading font-semibold text-white">{title}</span>
            {badge && (
              <span className="text-[10px] font-mono text-gold bg-gold/10 px-1.5 py-0.5 rounded">
                {badge}
              </span>
            )}
            {status === 'signed' && (
              <span className="flex items-center gap-1 text-[10px] text-success">
                <CheckCircle2 className="w-3 h-3" /> Signed
              </span>
            )}
          </div>
          {subtitle && (
            <span className="text-xs font-mono text-gray-500 block truncate">
              {subtitle}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {isOpen ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </span>
      </button>

      {isOpen && (
        <div className="mt-4 pt-4 border-t border-border-light animate-fade-in">
          {children}
        </div>
      )}
    </div>
  )
}

// --- Package Summary ---
function PackageSummary({ pkg }) {
  return (
    <div className="space-y-4">
      {/* Flights */}
      {pkg.flights?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Flights
          </h4>
          {pkg.flights.map((f, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg mb-2">
              <div>
                <p className="text-white text-sm font-medium">
                  {f.airline} {f.flight_number}
                </p>
                <p className="text-xs text-gray-400">
                  {f.departure_city} &rarr; {f.arrival_city}
                </p>
              </div>
              <span className="text-gold text-sm font-semibold">
                ${f.price_per_person_usd}/pp
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Hotels */}
      {pkg.hotels?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Hotels
          </h4>
          {pkg.hotels.map((h, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg mb-2">
              <div>
                <p className="text-white text-sm font-medium">
                  {h.name}{' '}
                  <span className="text-yellow-400">{'\u2605'.repeat(h.star_rating || 4)}</span>
                </p>
                <p className="text-xs text-gray-400">
                  {h.nights} nights &bull; {h.room_type}
                </p>
              </div>
              <span className="text-gold text-sm font-semibold">
                ${h.price_per_night_usd}/night
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Activities */}
      {pkg.activities?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Activities
          </h4>
          {pkg.activities.map((a, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg mb-2">
              <div>
                <p className="text-white text-sm font-medium">{a.name}</p>
                <p className="text-xs text-gray-400">{a.duration}</p>
              </div>
              <span className="text-gold text-sm font-semibold">
                ${a.price_per_person_usd}/pp
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Total */}
      {pkg.total_usd && (
        <div className="flex justify-between items-center pt-3 border-t border-border-light">
          <span className="text-gray-400 font-medium">Package Total</span>
          <span className="text-gold text-xl font-bold">${pkg.total_usd.toLocaleString()}</span>
        </div>
      )}
    </div>
  )
}

// --- AP2 Explainer Panel ---
function AP2ExplainerPanel() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="card">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-gold" />
          <span className="font-heading font-semibold text-white">
            What is the AP2 Mandate Chain?
          </span>
        </div>
        <ChevronRight
          className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-90' : ''}`}
        />
      </button>

      {isOpen && (
        <div className="mt-4 pt-4 border-t border-border-light space-y-4 animate-fade-in">
          <p className="text-sm text-gray-300">
            AP2 (Agent Payments Protocol) creates a cryptographically-linked chain
            of mandates that ensures every agent-driven purchase is{' '}
            <strong className="text-white">authorized</strong>,{' '}
            <strong className="text-white">authentic</strong>, and{' '}
            <strong className="text-white">accountable</strong>.
          </p>

          <div className="space-y-3">
            <ExplainerItem
              title="Intent Mandate"
              desc="Captures what the user wants and their spending limits. Signed by the user's device key to prove authorization."
            />
            <ExplainerItem
              title="Cart Mandate"
              desc="The merchant's specific offer. Links back to the Intent Mandate. Signed by both user and merchant — any price change invalidates the hash."
            />
            <ExplainerItem
              title="Payment Mandate"
              desc="Authorizes the exact payment. Links to both prior mandates. Processed by the payment agent with tokenized credentials."
            />
          </div>

          <div className="p-3 bg-space-bg/50 rounded-lg">
            <p className="text-sm text-gold">
              Delegated Access: The agent signs mandates on the user&apos;s behalf after
              OTP verification — no manual signing required.
            </p>
            <p className="text-xs text-gray-400 mt-1">
              The complete chain provides a dispute-resolution audit trail.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// --- Small Helpers ---
function MiniStep({ icon: Icon, label }) {
  return (
    <div className="flex flex-col items-center gap-2 p-4 bg-white/[0.03] rounded-xl border border-white/[0.06]">
      <Icon className="w-6 h-6 text-gray-600" />
      <span className="text-xs text-gray-500 text-center">{label}</span>
    </div>
  )
}

function InfoField({ label, value, mono, highlight, success }) {
  return (
    <div className="bg-space-bg/50 rounded-lg px-3 py-2">
      <span className="text-xs text-gray-500 block">{label}</span>
      <span
        className={`text-sm block truncate ${
          highlight ? 'text-gold font-semibold' : success ? 'text-success font-medium' : 'text-white'
        } ${mono ? 'font-mono text-xs' : ''}`}
        title={value}
      >
        {value || '\u2014'}
      </span>
    </div>
  )
}

function ExplainerItem({ title, desc }) {
  return (
    <div className="flex gap-3">
      <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-white text-sm font-medium">{title}</p>
        <p className="text-xs text-gray-400">{desc}</p>
      </div>
    </div>
  )
}

function formatStage(stage) {
  if (!stage) return ''
  return stage
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}
