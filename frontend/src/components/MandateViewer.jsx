import React, { useState, useMemo } from 'react'
import { Eye, Code, AlertTriangle, CheckCircle2, Copy, Check } from 'lucide-react'

export default function MandateViewer({ mandate, type }) {
  const [mode, setMode] = useState('visual') // 'visual' or 'raw'
  const [editedJson, setEditedJson] = useState(null)
  const [copied, setCopied] = useState(false)

  const jsonString = useMemo(() => {
    return JSON.stringify(mandate, null, 2)
  }, [mandate])

  const isModified = editedJson !== null && editedJson !== jsonString

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const renderJsonWithSyntax = (json) => {
    return json
      .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
      .replace(/: "([^"]*)"(,?)/g, ': <span class="json-string">"$1"</span>$2')
      .replace(/: (\d+\.?\d*)(,?)/g, ': <span class="json-number">$1</span>$2')
      .replace(/: (true|false)(,?)/g, ': <span class="json-boolean">$1</span>$2')
      .replace(/: (null)(,?)/g, ': <span class="json-boolean">$1</span>$2')
  }

  return (
    <div className="rounded-lg border border-border-light overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between bg-space-bg/50 px-4 py-2 border-b border-border-light">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">{type}</span>
          {isModified ? (
            <span className="flex items-center gap-1 text-xs text-red-400">
              <AlertTriangle className="w-3 h-3" />
              Modified - Signature Invalid
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-success">
              <CheckCircle2 className="w-3 h-3" />
              Signature Valid
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white px-2 py-1 rounded"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                Copy
              </>
            )}
          </button>

          <div className="flex rounded-md overflow-hidden border border-border-light">
            <button
              onClick={() => setMode('visual')}
              className={`flex items-center gap-1 px-3 py-1 text-xs transition-colors ${
                mode === 'visual'
                  ? 'bg-gold text-space-bg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Eye className="w-3 h-3" />
              Visual
            </button>
            <button
              onClick={() => setMode('raw')}
              className={`flex items-center gap-1 px-3 py-1 text-xs transition-colors ${
                mode === 'raw'
                  ? 'bg-gold text-space-bg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Code className="w-3 h-3" />
              Raw JSON
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-h-96 overflow-auto">
        {mode === 'visual' ? (
          <VisualMandateView mandate={mandate} type={type} />
        ) : (
          <div className="p-4 bg-space-bg">
            <pre
              className="text-xs font-mono whitespace-pre-wrap"
              dangerouslySetInnerHTML={{
                __html: renderJsonWithSyntax(jsonString),
              }}
            />
          </div>
        )}
      </div>

      {/* Tamper Detection */}
      {isModified && (
        <div className="px-4 py-2 bg-red-500/10 border-t border-red-500/30">
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>
              ⚠️ Signature Invalid — Mandate Tampered
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

// Visual representation of mandate
function VisualMandateView({ mandate, type }) {
  if (!mandate) return null

  return (
    <div className="p-4 space-y-3">
      {/* Core fields */}
      <div className="grid grid-cols-2 gap-3">
        <FieldDisplay label="Mandate ID" value={mandate.mandate_id} mono />
        <FieldDisplay label="Version" value={mandate.version} />
        <FieldDisplay label="Issued At" value={formatDate(mandate.issued_at)} />
        {mandate.expires_at && (
          <FieldDisplay label="Expires At" value={formatDate(mandate.expires_at)} />
        )}
      </div>

      {/* Type-specific fields */}
      {type === 'IntentMandate' && (
        <>
          <SectionHeader title="Shopping Intent" />
          {mandate.shopping_intent && (
            <div className="grid grid-cols-2 gap-3">
              <FieldDisplay
                label="Destination"
                value={mandate.shopping_intent.destination}
              />
              <FieldDisplay
                label="Origin"
                value={mandate.shopping_intent.origin}
              />
              <FieldDisplay
                label="Travelers"
                value={mandate.shopping_intent.travelers}
              />
              <FieldDisplay
                label="Budget"
                value={`$${mandate.shopping_intent.budget_usd?.toLocaleString()}`}
              />
              <FieldDisplay
                label="Cabin Class"
                value={mandate.shopping_intent.cabin_class}
              />
            </div>
          )}

          <SectionHeader title="Spending Limits" />
          {mandate.spending_limits && (
            <div className="grid grid-cols-2 gap-3">
              <FieldDisplay
                label="Max Total"
                value={`$${mandate.spending_limits.max_total_usd?.toLocaleString()}`}
              />
              <FieldDisplay
                label="Max Per Transaction"
                value={`$${mandate.spending_limits.max_per_transaction_usd?.toLocaleString()}`}
              />
            </div>
          )}

          <SectionHeader title="Configuration" />
          <div className="grid grid-cols-2 gap-3">
            <FieldDisplay
              label="Refundability Required"
              value={mandate.refundability_required ? 'Yes' : 'No'}
              success={mandate.refundability_required}
            />
            <FieldDisplay
              label="User Confirmation"
              value={mandate.user_cart_confirmation_required ? 'Human Present' : 'Agent Mode'}
            />
          </div>
        </>
      )}

      {type === 'CartMandate' && (
        <>
          <SectionHeader title="Linkage" />
          <FieldDisplay
            label="Intent Mandate ID"
            value={mandate.intent_mandate_id}
            mono
          />

          <SectionHeader title="Payer" />
          {mandate.payer && (
            <div className="grid grid-cols-2 gap-3">
              <FieldDisplay label="Name" value={mandate.payer.display_name} />
              <FieldDisplay label="Email" value={mandate.payer.email} />
              <FieldDisplay label="User ID" value={mandate.payer.user_id} mono />
            </div>
          )}

          <SectionHeader title="Payee" />
          {mandate.payee && (
            <div className="grid grid-cols-2 gap-3">
              <FieldDisplay label="Merchant" value={mandate.payee.merchant_name} />
              <FieldDisplay label="ID" value={mandate.payee.merchant_id} mono />
            </div>
          )}

          <SectionHeader title="Amounts" />
          {mandate.amounts && (
            <div className="grid grid-cols-4 gap-3">
              <FieldDisplay
                label="Subtotal"
                value={`$${mandate.amounts.subtotal_usd?.toFixed(2)}`}
              />
              <FieldDisplay
                label="Taxes"
                value={`$${mandate.amounts.taxes_usd?.toFixed(2)}`}
              />
              <FieldDisplay
                label="Fees"
                value={`$${mandate.amounts.fees_usd?.toFixed(2)}`}
              />
              <FieldDisplay
                label="Total"
                value={`$${mandate.amounts.total_usd?.toFixed(2)}`}
                highlight
              />
            </div>
          )}

          <SectionHeader title="Payment Method" />
          {mandate.payment_method && (
            <div className="grid grid-cols-3 gap-3">
              <FieldDisplay label="Type" value={mandate.payment_method.type} />
              <FieldDisplay label="Network" value={mandate.payment_method.network} />
              <FieldDisplay label="Last 4" value={mandate.payment_method.last4} />
              <FieldDisplay label="Token" value={mandate.payment_method.token} mono />
            </div>
          )}

          <SectionHeader title="Security" />
          <div className="space-y-2">
            <FieldDisplay label="Cart Hash" value={mandate.cart_hash} mono />
            <FieldDisplay
              label="User Signature"
              value={mandate.user_signature || 'Pending'}
              mono
            />
            <FieldDisplay
              label="Merchant Signature"
              value={mandate.merchant_signature || 'Pending'}
              mono
            />
          </div>
        </>
      )}

      {type === 'PaymentMandate' && (
        <>
          <SectionHeader title="Linkage" />
          <div className="grid grid-cols-2 gap-3">
            <FieldDisplay
              label="Cart Mandate ID"
              value={mandate.cart_mandate_id}
              mono
            />
            <FieldDisplay
              label="Intent Mandate ID"
              value={mandate.intent_mandate_id}
              mono
            />
          </div>

          <SectionHeader title="Transaction" />
          <div className="grid grid-cols-2 gap-3">
            <FieldDisplay label="Agent Presence" value={mandate.agent_presence} />
            <FieldDisplay
              label="Shopping Agent"
              value={mandate.shopping_agent_id}
              mono
            />
          </div>

          {mandate.payment_details && (
            <>
              <SectionHeader title="Payment Details" />
              <div className="grid grid-cols-2 gap-3">
                <FieldDisplay
                  label="Payment ID"
                  value={mandate.payment_details.payment_id}
                  mono
                />
                <FieldDisplay
                  label="Method"
                  value={mandate.payment_details.method_name}
                />
                <FieldDisplay
                  label="Total"
                  value={`$${mandate.payment_details.total?.total_usd?.toFixed(2)}`}
                  highlight
                />
                <FieldDisplay
                  label="Refund Period"
                  value={`${mandate.payment_details.refund_period_days} days`}
                />
              </div>
            </>
          )}

          <SectionHeader title="Authorization" />
          <FieldDisplay
            label="User Authorization Hash"
            value={mandate.user_authorization}
            mono
          />
        </>
      )}

      {/* Signature */}
      {mandate.signature && (
        <>
          <SectionHeader title="Signature" />
          <FieldDisplay label="HMAC-SHA256" value={mandate.signature} mono />
        </>
      )}
    </div>
  )
}

// Helper components
function SectionHeader({ title }) {
  return (
    <div className="pt-3 pb-1 border-t border-border-light">
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        {title}
      </h4>
    </div>
  )
}

function FieldDisplay({ label, value, mono, highlight, success }) {
  return (
    <div className="bg-space-bg rounded px-3 py-2">
      <span className="text-xs text-gray-500 block">{label}</span>
      <span
        className={`text-sm block truncate ${
          highlight
            ? 'text-gold font-semibold'
            : success
            ? 'text-success'
            : 'text-white'
        } ${mono ? 'font-mono text-xs' : ''}`}
        title={value}
      >
        {value || '-'}
      </span>
    </div>
  )
}

function formatDate(dateString) {
  if (!dateString) return '-'
  try {
    return new Date(dateString).toLocaleString()
  } catch {
    return dateString
  }
}
