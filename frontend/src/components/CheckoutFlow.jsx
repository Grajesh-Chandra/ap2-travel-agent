import React, { useState, useEffect } from 'react'
import {
  Target,
  ShoppingCart,
  CreditCard,
  FileCheck,
  CheckCircle2,
  ChevronRight,
  Lock,
  Shield,
  AlertCircle,
  Loader2,
  Download,
  Eye,
  Fingerprint,
} from 'lucide-react'
import MandateViewer from './MandateViewer'

const API_BASE = ''

export default function CheckoutFlow({ sessionData, selectedPackage, onComplete }) {
  const [currentStep, setCurrentStep] = useState(1)
  const [intentSigned, setIntentSigned] = useState(false)
  const [paymentMethods, setPaymentMethods] = useState([])
  const [selectedPaymentToken, setSelectedPaymentToken] = useState(null)
  const [cartMandate, setCartMandate] = useState(null)
  const [cartSigned, setCartSigned] = useState(false)
  const [confirmation, setConfirmation] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [partialCart, setPartialCart] = useState(null)
  const [error, setError] = useState(null)

  const steps = [
    { id: 1, title: 'Intent Capture', icon: Target },
    { id: 2, title: 'Merchant Cart', icon: ShoppingCart },
    { id: 3, title: 'Payment Method', icon: CreditCard },
    { id: 4, title: 'Cart Mandate', icon: FileCheck },
    { id: 5, title: 'Confirmation', icon: CheckCircle2 },
  ]

  // Fetch payment methods when reaching step 3
  useEffect(() => {
    if (currentStep === 3 && sessionData?.session_id) {
      fetchPaymentMethods()
    }
  }, [currentStep, sessionData])

  const fetchPaymentMethods = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/payment-methods`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionData.session_id }),
      })
      const data = await response.json()
      if (data.success) {
        setPaymentMethods(data.payment_methods)
      }
    } catch (err) {
      console.error('Failed to fetch payment methods:', err)
      // Use mock data as fallback
      setPaymentMethods([
        { token: 'tok_visa_4242', type: 'CARD', network: 'Visa', last4: '4242' },
        { token: 'tok_mc_5555', type: 'CARD', network: 'Mastercard', last4: '5555' },
        { token: 'tok_amex_1111', type: 'CARD', network: 'Amex', last4: '1111' },
      ])
    }
  }

  const handleSignIntent = async () => {
    setIsProcessing(true)
    // Simulate signing animation
    await new Promise((r) => setTimeout(r, 1500))
    setIntentSigned(true)
    setIsProcessing(false)

    // Select package
    if (sessionData?.session_id && selectedPackage) {
      try {
        const response = await fetch(`${API_BASE}/api/select-package`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionData.session_id,
            package_id: selectedPackage.package_id,
          }),
        })
        const data = await response.json()
        if (data.success) {
          setPartialCart(data.partial_cart)
        }
      } catch (err) {
        console.error('Failed to select package:', err)
      }
    }

    setTimeout(() => setCurrentStep(2), 500)
  }

  const handleSelectPayment = async (token) => {
    setSelectedPaymentToken(token)
    setIsProcessing(true)

    try {
      const response = await fetch(`${API_BASE}/api/create-cart-mandate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionData.session_id,
          payment_token: token,
        }),
      })
      const data = await response.json()
      if (data.success) {
        setCartMandate(data.cart_mandate)
        setCurrentStep(4)
      } else {
        setError(data.error)
      }
    } catch (err) {
      console.error('Failed to create cart mandate:', err)
      setError('Failed to create cart mandate')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleSignCart = async () => {
    setIsProcessing(true)
    await new Promise((r) => setTimeout(r, 2000))
    setCartSigned(true)
    setIsProcessing(false)
    setTimeout(() => processPayment(), 500)
  }

  const processPayment = async () => {
    setCurrentStep(5)
    setIsProcessing(true)

    try {
      const response = await fetch(`${API_BASE}/api/process-payment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionData.session_id }),
      })
      const data = await response.json()
      if (data.success) {
        setConfirmation(data.confirmation)
        onComplete?.(data.confirmation)
      } else {
        setError(data.error)
      }
    } catch (err) {
      console.error('Payment failed:', err)
      setError('Payment processing failed')
    } finally {
      setIsProcessing(false)
    }
  }

  if (!sessionData || !selectedPackage) {
    return (
      <div className="card text-center py-12">
        <AlertCircle className="w-12 h-12 text-gold mx-auto mb-4" />
        <h3 className="font-heading text-xl font-bold text-white mb-2">
          No Package Selected
        </h3>
        <p className="text-gray-400">
          Please go to Travel Planner and select a package first.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Progress Steps */}
      <div className="card">
        <div className="flex items-center justify-between">
          {steps.map((step, idx) => (
            <React.Fragment key={step.id}>
              <div
                className={`flex flex-col items-center ${
                  currentStep >= step.id ? 'text-gold' : 'text-gray-600'
                }`}
              >
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center border-2
                    ${
                      currentStep > step.id
                        ? 'bg-gold border-gold text-space-bg'
                        : currentStep === step.id
                        ? 'border-gold bg-gold/10'
                        : 'border-gray-700'
                    }`}
                >
                  {currentStep > step.id ? (
                    <CheckCircle2 className="w-6 h-6" />
                  ) : (
                    <step.icon className="w-5 h-5" />
                  )}
                </div>
                <span className="text-xs mt-2 font-medium">{step.title}</span>
              </div>
              {idx < steps.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 ${
                    currentStep > step.id ? 'bg-gold' : 'bg-gray-700'
                  }`}
                />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div className="animate-fade-in">
        {currentStep === 1 && (
          <IntentCaptureStep
            intentMandate={sessionData.intent_mandate}
            isSigned={intentSigned}
            isProcessing={isProcessing}
            onSign={handleSignIntent}
          />
        )}

        {currentStep === 2 && (
          <MerchantCartStep
            selectedPackage={selectedPackage}
            partialCart={partialCart}
            onContinue={() => setCurrentStep(3)}
          />
        )}

        {currentStep === 3 && (
          <PaymentMethodStep
            paymentMethods={paymentMethods}
            selectedToken={selectedPaymentToken}
            isProcessing={isProcessing}
            onSelect={handleSelectPayment}
            totalAmount={partialCart?.amounts?.total_usd || selectedPackage.total_usd}
          />
        )}

        {currentStep === 4 && (
          <CartMandateStep
            cartMandate={cartMandate}
            intentMandateId={sessionData.intent_mandate?.mandate_id}
            isSigned={cartSigned}
            isProcessing={isProcessing}
            onSign={handleSignCart}
          />
        )}

        {currentStep === 5 && (
          <ConfirmationStep
            confirmation={confirmation}
            isProcessing={isProcessing}
            error={error}
          />
        )}
      </div>

      {/* AP2 Explainer */}
      <AP2Explainer currentStep={currentStep} />
    </div>
  )
}

// Step 1: Intent Capture
function IntentCaptureStep({ intentMandate, isSigned, isProcessing, onSign }) {
  const [showRaw, setShowRaw] = useState(false)

  return (
    <div className="card card-gold">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Target className="w-6 h-6 text-gold" />
          <h2 className="font-heading text-xl font-bold text-white">
            Intent Mandate
          </h2>
        </div>
        <span className="text-xs font-mono text-gold bg-gold/10 px-2 py-1 rounded">
          AP2 v1
        </span>
      </div>

      <div className="space-y-4">
        <div className="bg-space-bg/50 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-400 mb-2">
            Natural Language
          </h4>
          <p className="text-white text-lg">
            "{intentMandate?.natural_language_description}"
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">Budget Cap</span>
            <p className="text-white font-semibold">
              ${intentMandate?.spending_limits?.max_total_usd?.toLocaleString()}
            </p>
          </div>
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">Payment Methods</span>
            <p className="text-white font-semibold">
              {intentMandate?.chargeable_payment_methods?.join(', ')}
            </p>
          </div>
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">Refundability</span>
            <p className="text-white font-semibold">
              {intentMandate?.refundability_required ? '✓ Required' : 'Not Required'}
            </p>
          </div>
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">User Confirmation</span>
            <p className="text-white font-semibold">
              {intentMandate?.user_cart_confirmation_required
                ? '✓ Human Present Mode'
                : 'Agent Mode'}
            </p>
          </div>
        </div>

        <div className="bg-space-bg/50 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-400 mb-2">
            Prompt Playback
          </h4>
          <p className="text-gray-300 italic">
            "{intentMandate?.prompt_playback}"
          </p>
        </div>

        <div className="flex items-center gap-4 pt-4 border-t border-border-light">
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white"
          >
            <Eye className="w-4 h-4" />
            {showRaw ? 'Hide' : 'View'} Raw Mandate JSON
          </button>
        </div>

        {showRaw && (
          <MandateViewer mandate={intentMandate} type="IntentMandate" />
        )}

        {isSigned ? (
          <div className="flex items-center gap-3 p-4 bg-success/10 rounded-lg border border-success/30">
            <CheckCircle2 className="w-6 h-6 text-success" />
            <div>
              <p className="text-success font-semibold">Mandate Signed ✓</p>
              <p className="text-xs font-mono text-gray-400">
                {intentMandate?.mandate_id}
              </p>
            </div>
          </div>
        ) : (
          <button
            onClick={onSign}
            disabled={isProcessing}
            className="w-full btn-gold py-3 flex items-center justify-center gap-3"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Signing...
              </>
            ) : (
              <>
                <Fingerprint className="w-5 h-5" />
                Sign Intent Mandate
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

// Step 2: Merchant Cart
function MerchantCartStep({ selectedPackage, partialCart, onContinue }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Selected Package */}
      <div className="lg:col-span-2">
        <div className="card">
          <h2 className="font-heading text-xl font-bold text-white mb-4">
            Selected Package: {selectedPackage.tier?.charAt(0).toUpperCase() + selectedPackage.tier?.slice(1)}
          </h2>

          <div className="space-y-4">
            {/* Flights */}
            <div>
              <h3 className="text-sm font-semibold text-gray-400 mb-2">Flights</h3>
              {selectedPackage.flights?.map((flight, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg mb-2"
                >
                  <div>
                    <p className="text-white font-medium">
                      {flight.airline} {flight.flight_number}
                    </p>
                    <p className="text-sm text-gray-400">
                      {flight.departure_city} → {flight.arrival_city}
                    </p>
                  </div>
                  <p className="text-gold font-semibold">
                    ${flight.price_per_person_usd}/person
                  </p>
                </div>
              ))}
            </div>

            {/* Hotels */}
            <div>
              <h3 className="text-sm font-semibold text-gray-400 mb-2">Hotels</h3>
              {selectedPackage.hotels?.map((hotel, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg mb-2"
                >
                  <div>
                    <p className="text-white font-medium">
                      {hotel.name}{' '}
                      <span className="text-yellow-400">
                        {'★'.repeat(hotel.star_rating || 4)}
                      </span>
                    </p>
                    <p className="text-sm text-gray-400">
                      {hotel.nights} nights • {hotel.room_type}
                    </p>
                  </div>
                  <p className="text-gold font-semibold">
                    ${hotel.price_per_night_usd}/night
                  </p>
                </div>
              ))}
            </div>

            {/* Activities */}
            <div>
              <h3 className="text-sm font-semibold text-gray-400 mb-2">Activities</h3>
              {selectedPackage.activities?.map((activity, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg mb-2"
                >
                  <div>
                    <p className="text-white font-medium">{activity.name}</p>
                    <p className="text-sm text-gray-400">{activity.duration}</p>
                  </div>
                  <p className="text-gold font-semibold">
                    ${activity.price_per_person_usd}/person
                  </p>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={onContinue}
            className="w-full mt-6 btn-gold py-3 flex items-center justify-center gap-2"
          >
            Continue to Payment
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Cart Summary */}
      <div className="lg:col-span-1">
        <div className="card card-gold sticky top-24">
          <h3 className="font-heading font-semibold text-white mb-4">
            Cart Summary
          </h3>

          {partialCart && (
            <>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Subtotal</span>
                  <span className="text-white">
                    ${partialCart.amounts?.subtotal_usd?.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Taxes</span>
                  <span className="text-white">
                    ${partialCart.amounts?.taxes_usd?.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Fees</span>
                  <span className="text-white">
                    ${partialCart.amounts?.fees_usd?.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between pt-3 border-t border-border-light">
                  <span className="text-white font-semibold">Total</span>
                  <span className="text-gold text-xl font-bold">
                    ${partialCart.amounts?.total_usd?.toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-border-light">
                <p className="text-xs text-gray-500">
                  Cart Hash (first 16 chars):
                </p>
                <p className="font-mono text-xs text-gray-400 truncate">
                  {/* Hash will be computed on backend */}
                  Computed on mandate creation...
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// Step 3: Payment Method
function PaymentMethodStep({
  paymentMethods,
  selectedToken,
  isProcessing,
  onSelect,
  totalAmount,
}) {
  const networkIcons = {
    Visa: '💳',
    Mastercard: '💳',
    Amex: '💳',
  }

  return (
    <div className="card">
      <h2 className="font-heading text-xl font-bold text-white mb-4">
        Select Payment Method
      </h2>

      <div className="space-y-3 mb-6">
        {paymentMethods.map((pm) => (
          <button
            key={pm.token}
            onClick={() => onSelect(pm.token)}
            disabled={isProcessing}
            className={`w-full flex items-center justify-between p-4 rounded-lg border
              transition-all ${
                selectedToken === pm.token
                  ? 'border-gold bg-gold/10'
                  : 'border-border-light bg-space-bg/50 hover:border-gold/50'
              }`}
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-8 bg-white/10 rounded flex items-center justify-center text-lg">
                {networkIcons[pm.network] || '💳'}
              </div>
              <div className="text-left">
                <p className="text-white font-medium">{pm.network}</p>
                <p className="text-sm text-gray-400">···· {pm.last4}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-gold font-semibold">
                ${totalAmount?.toLocaleString()}
              </p>
              {selectedToken === pm.token && isProcessing && (
                <Loader2 className="w-4 h-4 animate-spin text-gold ml-auto mt-1" />
              )}
            </div>
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 p-4 bg-space-bg/50 rounded-lg border border-border-light">
        <Lock className="w-5 h-5 text-success" />
        <div>
          <p className="text-sm text-success font-medium">
            Payment tokenized securely
          </p>
          <p className="text-xs text-gray-400">
            Card number never shared with merchant
          </p>
        </div>
      </div>

      <div className="mt-4 text-xs text-gray-500">
        <p>Credential Provider: VoyagerPay Vault</p>
        <p>Token issued by: credentials_agent (port 8002)</p>
      </div>
    </div>
  )
}

// Step 4: Cart Mandate
function CartMandateStep({
  cartMandate,
  intentMandateId,
  isSigned,
  isProcessing,
  onSign,
}) {
  const [showRaw, setShowRaw] = useState(false)

  if (!cartMandate) {
    return (
      <div className="card text-center py-8">
        <Loader2 className="w-8 h-8 animate-spin text-gold mx-auto mb-4" />
        <p className="text-gray-400">Creating cart mandate...</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading text-xl font-bold text-white">
          Cart Mandate Review
        </h2>
        <span className="text-xs font-mono text-gold bg-gold/10 px-2 py-1 rounded">
          AP2/v1
        </span>
      </div>

      <div className="space-y-4">
        {/* Linkage */}
        <div className="flex items-center gap-2 p-3 bg-space-bg/50 rounded-lg">
          <CheckCircle2 className="w-5 h-5 text-success" />
          <div>
            <span className="text-sm text-gray-400">Intent Mandate ID: </span>
            <span className="text-xs font-mono text-white">
              {intentMandateId}
            </span>
          </div>
        </div>

        {/* Payer/Payee */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">PAYER</span>
            <p className="text-white font-medium">
              {cartMandate.payer?.display_name}
            </p>
            <p className="text-xs text-gray-400">{cartMandate.payer?.email}</p>
          </div>
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">PAYEE</span>
            <p className="text-white font-medium">
              {cartMandate.payee?.merchant_name}
            </p>
          </div>
        </div>

        {/* Line Items */}
        <div className="bg-space-bg/50 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-gray-400 mb-3">
            LINE ITEMS
          </h4>
          <div className="space-y-2">
            {cartMandate.line_items?.map((item, idx) => (
              <div key={idx} className="flex justify-between text-sm">
                <span className="text-gray-300">
                  {item.description} ({item.quantity}x)
                </span>
                <span className="text-white font-mono">
                  ${item.total_usd?.toFixed(2)}
                </span>
              </div>
            ))}
            <div className="pt-3 mt-3 border-t border-border-light space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Subtotal</span>
                <span className="text-white">
                  ${cartMandate.amounts?.subtotal_usd?.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Taxes & Fees</span>
                <span className="text-white">
                  $
                  {(
                    (cartMandate.amounts?.taxes_usd || 0) +
                    (cartMandate.amounts?.fees_usd || 0)
                  ).toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between text-lg font-bold pt-2">
                <span className="text-white">TOTAL</span>
                <span className="text-gold">
                  ${cartMandate.amounts?.total_usd?.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Payment & Refund */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">Payment</span>
            <p className="text-white font-medium">
              {cartMandate.payment_method?.network} ····{' '}
              {cartMandate.payment_method?.last4}
            </p>
            <p className="text-xs font-mono text-gray-400">
              {cartMandate.payment_method?.token}
            </p>
          </div>
          <div className="bg-space-bg/50 rounded-lg p-3">
            <span className="text-sm text-gray-500">Refundable</span>
            <p className="text-success font-medium">
              ✓ {cartMandate.refund_policy?.refund_period_days}-day policy
            </p>
          </div>
        </div>

        {/* Cart Hash */}
        <div className="p-3 bg-space-bg/50 rounded-lg">
          <span className="text-sm text-gray-500">Cart Hash (SHA256)</span>
          <p className="font-mono text-xs text-gray-400 truncate">
            {cartMandate.cart_hash}
          </p>
        </div>

        {/* Warning */}
        <div className="p-4 bg-yellow-500/10 rounded-lg border border-yellow-500/30">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-yellow-400 font-medium">
                By signing, you cryptographically authorize this exact cart.
              </p>
              <p className="text-sm text-yellow-500/70 mt-1">
                Any modification will invalidate this mandate.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 pt-2">
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white"
          >
            <Eye className="w-4 h-4" />
            {showRaw ? 'Hide' : 'View'} Raw Mandate JSON
          </button>
        </div>

        {showRaw && <MandateViewer mandate={cartMandate} type="CartMandate" />}

        {isSigned ? (
          <div className="flex items-center gap-3 p-4 bg-success/10 rounded-lg border border-success/30">
            <CheckCircle2 className="w-6 h-6 text-success" />
            <div>
              <p className="text-success font-semibold">Cart Mandate Signed ✓</p>
              <p className="text-xs font-mono text-gray-400">
                Processing payment...
              </p>
            </div>
          </div>
        ) : (
          <button
            onClick={onSign}
            disabled={isProcessing}
            className="w-full btn-gold py-4 flex items-center justify-center gap-3"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Signing with Device Key...
              </>
            ) : (
              <>
                <Lock className="w-5 h-5" />
                Sign Cart Mandate with Device Key
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

// Step 5: Confirmation
function ConfirmationStep({ confirmation, isProcessing, error }) {
  if (error) {
    return (
      <div className="card bg-red-500/10 border-red-500/30">
        <div className="text-center py-8">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="font-heading text-2xl font-bold text-red-400 mb-2">
            Payment Failed
          </h2>
          <p className="text-gray-400">{error}</p>
        </div>
      </div>
    )
  }

  if (isProcessing || !confirmation) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <div className="space-y-4 text-sm font-mono text-left max-w-md mx-auto">
            <PaymentFlowLine
              from="ShoppingAgent"
              to="PaymentAgent"
              label="PaymentMandate sent"
              active
            />
            <PaymentFlowLine
              from="PaymentAgent"
              to="Card Network"
              label="Authorization request"
              pending
            />
            <PaymentFlowLine
              from="Card Network"
              to="PaymentAgent"
              label="Awaiting response..."
              pending
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card card-success">
      <div className="text-center py-6 mb-6 border-b border-border-light">
        <CheckCircle2 className="w-20 h-20 text-success mx-auto mb-4 animate-pulse-gold" />
        <h2 className="font-heading text-3xl font-bold text-success mb-2">
          BOOKING CONFIRMED
        </h2>
        <p className="text-gray-400">
          Your travel has been successfully booked!
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-space-bg/50 rounded-lg p-4">
          <span className="text-sm text-gray-500">Transaction ID</span>
          <p className="text-white font-mono">{confirmation.transaction_id}</p>
        </div>
        <div className="bg-space-bg/50 rounded-lg p-4">
          <span className="text-sm text-gray-500">Authorization Code</span>
          <p className="text-white font-mono">
            {confirmation.authorization_code}
          </p>
        </div>
      </div>

      {/* Booking References */}
      <div className="mb-6">
        <h3 className="font-heading font-semibold text-white mb-3">
          Booking References
        </h3>
        <div className="space-y-2">
          {confirmation.booking_references?.map((ref, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-3 bg-space-bg/50 rounded-lg"
            >
              <div>
                <span className="text-sm text-gray-400 capitalize">
                  {ref.item_type}
                </span>
                <p className="text-white">{ref.provider}</p>
              </div>
              <div className="text-right">
                <span className="text-sm text-gray-400">PNR</span>
                <p className="text-gold font-mono font-bold">{ref.pnr}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Audit Trail */}
      <div className="p-4 bg-space-bg/50 rounded-lg mb-6">
        <div className="flex items-center gap-2 mb-2">
          <Shield className="w-5 h-5 text-success" />
          <span className="text-white font-semibold">Liability Assignment</span>
        </div>
        <p className="text-gray-300">
          <span className="text-gold">{confirmation.liability_assignment}</span>{' '}
          (Human-Present transaction)
        </p>
        <p className="text-sm text-gray-400 mt-2">
          Audit Trail: {confirmation.audit_trail}
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-4">
        <button className="flex-1 btn-gold py-3 flex items-center justify-center gap-2">
          <Download className="w-5 h-5" />
          Download Itinerary PDF
        </button>
        <button className="flex-1 py-3 rounded-lg border border-gold/30 text-gold hover:bg-gold/10 transition-colors">
          View Full Audit Trail
        </button>
      </div>
    </div>
  )
}

// Payment Flow Line Component
function PaymentFlowLine({ from, to, label, active, pending }) {
  return (
    <div
      className={`flex items-center gap-3 p-2 rounded ${
        active
          ? 'bg-gold/10 text-gold'
          : pending
          ? 'text-gray-500'
          : 'text-success'
      }`}
    >
      <span className="text-xs">{from}</span>
      <span>→</span>
      <span className="text-xs">{to}</span>
      <span className="flex-1" />
      <span className="text-xs">
        [{label}]
        {active && <Loader2 className="w-3 h-3 inline ml-2 animate-spin" />}
      </span>
    </div>
  )
}

// AP2 Explainer Panel
function AP2Explainer({ currentStep }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="card">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-gold" />
          <span className="font-heading font-semibold text-white">
            AP2 Explainer
          </span>
        </div>
        <ChevronRight
          className={`w-5 h-5 text-gray-400 transition-transform ${
            isOpen ? 'rotate-90' : ''
          }`}
        />
      </button>

      {isOpen && (
        <div className="mt-4 pt-4 border-t border-border-light space-y-4 animate-fade-in">
          <div>
            <h4 className="font-semibold text-white mb-2">
              Why AP2 matters for travel booking:
            </h4>
            <ul className="space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                <span className="text-gray-300">
                  <strong>Authorization</strong> — Signed mandate proves user
                  authorized THIS exact trip
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                <span className="text-gray-300">
                  <strong>Authenticity</strong> — Cart hash proves no price or
                  item was changed by the agent
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                <span className="text-gray-300">
                  <strong>Accountability</strong> — Complete chain: Intent →
                  Cart → Payment for disputes
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                <span className="text-gray-300">
                  <strong>Privacy</strong> — Payment token never shared with
                  merchant directly
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0 mt-0.5" />
                <span className="text-gray-300">
                  <strong>Interoperable</strong> — Any AP2-compliant agent can
                  transact with any merchant
                </span>
              </li>
            </ul>
          </div>

          <div className="p-3 bg-space-bg/50 rounded-lg">
            <p className="text-sm text-gold">
              This transaction mode: <strong>Human Present</strong>
            </p>
            <p className="text-xs text-gray-400 mt-1">
              The user reviewed and signed both mandates in-session
            </p>
            <p className="text-xs text-gray-400">
              Liability assignment: Merchant (standard chargeback rules apply)
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
