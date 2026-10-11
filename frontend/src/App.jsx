import { useState, useRef, useEffect, useCallback } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ── Utilities ────────────────────────────────────────────────────────────────

async function detectCountryCode() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve({ code: 'us', status: 'unavailable' })
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const resp = await fetch(
            `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${coords.latitude}&longitude=${coords.longitude}&localityLanguage=en`
          )
          const data = await resp.json()
          resolve({ code: (data.countryCode || 'us').toLowerCase(), status: 'found' })
        } catch {
          resolve({ code: 'us', status: 'found' })
        }
      },
      () => resolve({ code: 'us', status: 'denied' }),
      { timeout: 5000 }
    )
  })
}

function getToken() { return localStorage.getItem('bb_token') }
function setToken(t) { localStorage.setItem('bb_token', t) }
function clearToken() { localStorage.removeItem('bb_token') }

async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`${API_BASE_URL}${path}`, { ...options, headers })
}

// ── Auth modal (login + register with membership step) ───────────────────────

function AuthModal({ onClose, onSuccess, availableMemberships }) {
  const [tab, setTab] = useState('login')
  // Step within register: 'details' → 'memberships'
  const [registerStep, setRegisterStep] = useState('details')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [age, setAge] = useState('')
  const [selectedMemberships, setSelectedMemberships] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const toggleMembership = (id) =>
    setSelectedMemberships(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    )

  // Step 1: validate details and move to membership selection
  const handleDetailsNext = (e) => {
    e.preventDefault()
    setError('')
    if (!email || !password) return setError('Email and password are required')
    if (password.length < 6) return setError('Password must be at least 6 characters')
    setRegisterStep('memberships')
  }

  // Step 2: submit with all data
  const handleRegisterSubmit = async () => {
    setError('')
    setLoading(true)
    try {
      const resp = await fetch(`${API_BASE_URL}/api/users/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          age: age ? parseInt(age) : null,
          memberships: selectedMemberships,
        }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Registration failed')
      setToken(data.access_token)
      onSuccess(data.user)
    } catch (err) {
      setError(err.message)
      setRegisterStep('details') // go back on error
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const form = new URLSearchParams({ username: email, password })
      const resp = await fetch(`${API_BASE_URL}/api/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Login failed')
      setToken(data.access_token)
      onSuccess(data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const switchTab = (t) => {
    setTab(t)
    setRegisterStep('details')
    setError('')
    setSelectedMemberships([])
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>

        <div className="modal-tabs">
          <button className={tab === 'login' ? 'active' : ''} onClick={() => switchTab('login')}>Sign in</button>
          <button className={tab === 'register' ? 'active' : ''} onClick={() => switchTab('register')}>Register</button>
        </div>

        {tab === 'login' && (
          <form onSubmit={handleLogin} className="auth-form">
            <label>Email
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            </label>
            <label>Password
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
            </label>
            {error && <p className="auth-error">{error}</p>}
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? '…' : 'Sign in'}
            </button>
          </form>
        )}

        {tab === 'register' && registerStep === 'details' && (
          <form onSubmit={handleDetailsNext} className="auth-form">
            <p className="register-step-label">Step 1 of 2 — Account details</p>
            <label>Email
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            </label>
            <label>Password
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={6} />
            </label>
            <label>Age <span className="optional">(optional)</span>
              <input type="number" value={age} onChange={e => setAge(e.target.value)} min={1} max={120} />
            </label>
            {error && <p className="auth-error">{error}</p>}
            <button type="submit" className="auth-submit">Next →</button>
          </form>
        )}

        {tab === 'register' && registerStep === 'memberships' && (
          <div className="auth-form">
            <p className="register-step-label">Step 2 of 2 — Your store memberships</p>
            <p className="register-step-hint">
              Select the stores you're a member of. We'll apply your discounts automatically when searching.
            </p>
            <div className="memberships-list register-memberships">
              {availableMemberships.map(p => {
                const checked = selectedMemberships.includes(p.id)
                return (
                  <label
                    key={p.id}
                    className={`membership-chip ${checked ? 'active' : ''}`}
                    title={p.description}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMembership(p.id)}
                    />
                    <span className="membership-chip-store">{p.store}</span>
                    <span className="membership-chip-name">{p.name}</span>
                    {p.discount_pct > 0 && (
                      <span className="discount-badge">{p.discount_pct}% off</span>
                    )}
                  </label>
                )
              })}
            </div>
            {error && <p className="auth-error">{error}</p>}
            <div className="register-actions">
              <button className="auth-back" onClick={() => setRegisterStep('details')}>← Back</button>
              <button className="auth-submit" onClick={handleRegisterSubmit} disabled={loading}>
                {loading ? '…' : 'Create account'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Profile panel ────────────────────────────────────────────────────────────

function ProfilePanel({ user, availableMemberships, onUpdate, onLogout }) {
  const [age, setAge] = useState(user.age ?? '')
  const [memberships, setMemberships] = useState(user.memberships || [])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const save = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const resp = await apiFetch('/api/users/me', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ age: age ? parseInt(age) : null, memberships }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail)
      onUpdate(data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      alert('Save failed: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="profile-panel">
      <div className="profile-header">
        <span className="profile-email">👤 {user.email}</span>
        <button className="profile-logout" onClick={onLogout}>Sign out</button>
      </div>
      <div className="profile-body">
        <label className="profile-field">Age
          <input type="number" value={age} onChange={e => setAge(e.target.value)} min={1} max={120} />
        </label>
        <p className="memberships-label">My memberships</p>
        <div className="memberships-list">
          {availableMemberships.map(p => {
            const checked = memberships.includes(p.id)
            return (
              <label key={p.id} className={`membership-chip ${checked ? 'active' : ''}`} title={p.description}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => setMemberships(checked ? memberships.filter(m => m !== p.id) : [...memberships, p.id])}
                />
                {p.name}
                {p.discount_pct > 0 && <span className="discount-badge">{p.discount_pct}% off</span>}
              </label>
            )
          })}
        </div>
        <button className="profile-save" onClick={save} disabled={saving}>
          {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </div>
  )
}

// ── Size + Color filters ─────────────────────────────────────────────────────

const COLOR_HEX = {
  Black: '#111', White: '#f5f5f5', Grey: '#9e9e9e', Navy: '#1a237e',
  Blue: '#1565c0', Red: '#c62828', Green: '#2e7d32', Beige: '#d4c5a9',
  Brown: '#4e342e', Pink: '#f06292', Yellow: '#f9a825', Purple: '#6a1b9a',
  Orange: '#e65100', Khaki: '#8d8c5e', Cream: '#fffdd0', Burgundy: '#800020',
}

function SizeColorFilters({ productType, sizes, colors, selectedSize, selectedColor, onSizeChange, onColorChange }) {
  if (!productType || productType === 'unknown') return null
  return (
    <div className="filters">
      <div className="filter-group">
        <span className="filter-label">Size</span>
        <div className="filter-options">
          <button className={`filter-chip ${!selectedSize ? 'active' : ''}`} onClick={() => onSizeChange('')}>Any</button>
          {sizes.map(s => (
            <button key={s} className={`filter-chip ${selectedSize === s ? 'active' : ''}`}
              onClick={() => onSizeChange(selectedSize === s ? '' : s)}>{s}</button>
          ))}
        </div>
      </div>
      <div className="filter-group">
        <span className="filter-label">Color</span>
        <div className="filter-options">
          <button className={`filter-chip ${!selectedColor ? 'active' : ''}`} onClick={() => onColorChange('')}>Any</button>
          {colors.map(c => (
            <button key={c}
              className={`filter-chip color-chip ${selectedColor === c ? 'active' : ''}`}
              onClick={() => onColorChange(selectedColor === c ? '' : c)}
              style={{ '--chip-color': COLOR_HEX[c] || '#ccc' }}>
              <span className="color-dot" />{c}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Other small components ───────────────────────────────────────────────────

function MembershipSelector({ memberships, available, onChange }) {
  return (
    <div className="memberships">
      <p className="memberships-label">Your memberships</p>
      <div className="memberships-list">
        {available.map(p => {
          const checked = memberships.includes(p.id)
          return (
            <label key={p.id} className={`membership-chip ${checked ? 'active' : ''}`} title={p.description}>
              <input type="checkbox" checked={checked}
                onChange={() => onChange(checked ? memberships.filter(m => m !== p.id) : [...memberships, p.id])} />
              {p.name}
              {p.discount_pct > 0 && <span className="discount-badge">{p.discount_pct}% off</span>}
            </label>
          )
        })}
      </div>
    </div>
  )
}

function PriceCell({ price, currency, discountedPrice, discountPct, membershipName, clubPrice, salePrice }) {
  if (price == null && clubPrice == null && salePrice == null) return <td>—</td>
  if (clubPrice != null && discountedPrice == null) {
    return <td><span className="price-with-discount">
      <span className="price-original">{price} {currency}</span>
      <span className="price-discounted">{clubPrice} {currency}</span>
      <span className="discount-tag">מועדון</span>
    </span></td>
  }
  if (salePrice != null && salePrice !== price) {
    return <td><span className="price-with-discount">
      <span className="price-original">{price} {currency}</span>
      <span className="price-discounted">{salePrice} {currency}</span>
      <span className="discount-tag">מבצע</span>
    </span></td>
  }
  if (discountedPrice != null && discountPct > 0) {
    return <td><span className="price-with-discount">
      <span className="price-original">{price} {currency}</span>
      <span className="price-discounted">{discountedPrice} {currency}</span>
      <span className="discount-tag" title={membershipName}>-{discountPct}%</span>
    </span></td>
  }
  return <td><span>{price} {currency}</span></td>
}

// Garment nouns Shein's keyword search matches well. We pick the one present
// in the query (plus a key descriptor like "lace" and the color) to form a
// short, high-recall Shein search — long phrases return "No matches found".
const SHEIN_GARMENTS = [
  'dress', 'top', 'blouse', 'shirt', 't-shirt', 'tee', 'crop top', 'tank top',
  'skirt', 'pants', 'trousers', 'jeans', 'shorts', 'leggings', 'jacket',
  'coat', 'hoodie', 'sweater', 'cardigan', 'bodysuit', 'jumpsuit', 'romper',
  'bikini', 'swimsuit', 'lingerie', 'bra', 'sneakers', 'shoes', 'boots', 'sandals',
]
const SHEIN_DESCRIPTORS = [
  'lace', 'floral', 'knit', 'denim', 'satin', 'mesh', 'ribbed', 'cutout',
  'hollow out', 'oversized', 'cropped', 'bodycon', 'pleated', 'sequin',
]

function sheinUrl(host) {
  return (q, _size, color) => {
    const lower = (q || '').toLowerCase()
    // Pick the most specific garment noun present (longest match wins)
    let garment = ''
    for (const g of SHEIN_GARMENTS) {
      if (lower.includes(g) && g.length > garment.length) garment = g
    }
    // Pick one descriptor if present (e.g. "lace")
    const descriptor = SHEIN_DESCRIPTORS.find(d => lower.includes(d)) || ''
    // Build a short term: [descriptor] [garment] [color], falling back to raw query
    const parts = [descriptor, garment, color].filter(Boolean)
    const term = parts.length ? parts.join(' ') : (q || '').split(/\s+/).slice(0, 3).join(' ')
    return `https://${host}/pdsearch/${encodeURIComponent(term)}/`
  }
}

const STORE_LINKS = {
  il: [
    {
      id: 'zara', label: 'Zara', logo: '🛍️',
      // Zara search: include color in the search term — closest we can get
      url: (q, _size, color) => {
        const term = [q, color].filter(Boolean).join(' ')
        return `https://www.zara.com/il/en/search?searchTerm=${encodeURIComponent(term)}`
      },
      membershipIds: ['zara_member', 'zara_student'], membershipNote: 'Your Zara discount applies at checkout',
    },
    {
      id: 'shein', label: 'Shein', logo: '🧥',
      url: sheinUrl('il.shein.com'),
      membershipIds: [], membershipNote: '',
    },
    {
      id: 'asos', label: 'ASOS', logo: '👟',
      // ASOS search supports colour and size query params
      url: (q, size, color) => {
        const params = new URLSearchParams({ q })
        if (color) params.set('colour', color.toLowerCase())
        if (size) params.set('size', size)
        return `https://www.asos.com/search/?${params}`
      },
      membershipIds: ['asos_premier', 'asos_student'], membershipNote: 'Your ASOS membership applies at checkout',
    },
  ],
  gb: [
    {
      id: 'asos', label: 'ASOS', logo: '👟',
      url: (q, size, color) => {
        const params = new URLSearchParams({ q })
        if (color) params.set('colour', color.toLowerCase())
        if (size) params.set('size', size)
        return `https://www.asos.com/search/?${params}`
      },
      membershipIds: ['asos_premier', 'asos_student'], membershipNote: 'Your ASOS membership applies at checkout',
    },
    {
      id: 'zara', label: 'Zara', logo: '🛍️',
      url: (q, _size, color) => {
        const term = [q, color].filter(Boolean).join(' ')
        return `https://www.zara.com/uk/en/search?searchTerm=${encodeURIComponent(term)}`
      },
      membershipIds: ['zara_member', 'zara_student'], membershipNote: 'Your Zara discount applies at checkout',
    },
    {
      id: 'shein', label: 'Shein', logo: '🧥',
      url: sheinUrl('www.shein.co.uk'),
      membershipIds: [], membershipNote: '',
    },
  ],
  us: [
    {
      id: 'asos', label: 'ASOS', logo: '👟',
      url: (q, size, color) => {
        const params = new URLSearchParams({ q })
        if (color) params.set('colour', color.toLowerCase())
        if (size) params.set('size', size)
        return `https://www.asos.com/us/search/?${params}`
      },
      membershipIds: ['asos_premier', 'asos_student'], membershipNote: 'Your ASOS membership applies at checkout',
    },
    {
      id: 'zara', label: 'Zara', logo: '🛍️',
      url: (q, _size, color) => {
        const term = [q, color].filter(Boolean).join(' ')
        return `https://www.zara.com/us/en/search?searchTerm=${encodeURIComponent(term)}`
      },
      membershipIds: ['zara_member', 'zara_student'], membershipNote: 'Your Zara discount applies at checkout',
    },
    {
      id: 'shein', label: 'Shein', logo: '🧥',
      url: sheinUrl('us.shein.com'),
      membershipIds: [], membershipNote: '',
    },
  ],
}

function StoreLinks({ query, countryCode, memberships, size, color }) {
  if (!query) return null
  const stores = STORE_LINKS[(countryCode || 'us').toLowerCase()] || STORE_LINKS['us']
  return (
    <div className="store-links">
      <p className="store-links-label">
        These stores don't list on Google Shopping — search them directly
        {(size || color) && <span className="store-links-filter-note"> with your filters pre-applied</span>}:
      </p>
      <div className="store-links-list">
        {stores.map(store => {
          const hasMembership = memberships?.some(m => store.membershipIds.includes(m))
          return (
            <a key={store.id} href={store.url(query, size, color)} target="_blank" rel="noreferrer"
              className={`store-link-card ${hasMembership ? 'has-membership' : ''}`}>
              <span className="store-link-logo">{store.logo}</span>
              <div className="store-link-body">
                <span className="store-link-name">{store.label}</span>
                {(size || color) && (
                  <span className="store-link-filters">
                    {[color, size && `Size ${size}`].filter(Boolean).join(' · ')}
                  </span>
                )}
                {hasMembership && <span className="store-link-membership-note">{store.membershipNote}</span>}
              </div>
              <span className="store-link-arrow">→</span>
            </a>
          )
        })}
      </div>
    </div>
  )
}

// ── Coupon badge ─────────────────────────────────────────────────────────────

function CouponBadge({ code, description, sourceUrl, isTrusted }) {
  const [copied, setCopied] = useState(false)

  const copy = (e) => {
    e.preventDefault()
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <a
      href={sourceUrl || '#'}
      target="_blank"
      rel="noreferrer"
      className={`coupon-badge ${isTrusted ? 'trusted' : ''}`}
      title={description}
      onClick={copy}
    >
      <span className="coupon-code">{code}</span>
      <span className="coupon-copy">{copied ? '✓' : 'Copy'}</span>
    </a>
  )
}

function StoreCoupons({ storeName, coupons }) {
  if (!coupons || coupons.length === 0) return null
  return (
    <div className="store-coupons">
      <span className="store-coupons-label">🏷️ Coupons:</span>
      {coupons.map((c, i) => (
        <CouponBadge
          key={i}
          code={c.code}
          description={c.description}
          sourceUrl={c.source_url}
          isTrusted={c.is_trusted}
        />
      ))}
    </div>
  )
}

// ── Build product URL helper ──────────────────────────────────────────────────
function buildProductUrl(url, store, color) {
  if (!url || url === '#' || !color) return url
  const storeLower = (store || '').toLowerCase()
  try {
    if (storeLower.includes('asos')) {
      const u = new URL(url)
      u.searchParams.set('colour', color.toLowerCase())
      return u.toString()
    }
  } catch { /* invalid URL — return as-is */ }
  return url
}

function LocationBadge({ countryCode }) {
  if (!countryCode) return null
  return <span className="location-badge" title="Results localised to your region">📍 {countryCode.toUpperCase()}</span>
}

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  // Auth
  const [user, setUser] = useState(null)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [showProfile, setShowProfile] = useState(false)

  // Search mode
  const [mode, setMode] = useState('text')

  // Text search
  const [query, setQuery] = useState('')

  // Image search — two-phase state machine
  // imagePhase: 'idle' | 'identifying' | 'filters' | 'searching' | 'results'
  const [imageFile, setImageFile] = useState(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null)
  const [imagePhase, setImagePhase] = useState('idle')

  // Results
  const [results, setResults] = useState([])
  const [searchStatus, setSearchStatus] = useState('idle') // for text search
  const [errorMessage, setErrorMessage] = useState('')
  const [identifiedAs, setIdentifiedAs] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')  // cleaned term for store links

  // Location
  const [countryCode, setCountryCode] = useState(null)
  const [locationStatus, setLocationStatus] = useState('idle')

  // Memberships
  const [memberships, setMemberships] = useState([])
  const [availableMemberships, setAvailableMemberships] = useState([])

  // Size / color filters
  const [productType, setProductType] = useState(null)
  const [availableSizes, setAvailableSizes] = useState([])
  const [availableColors, setAvailableColors] = useState([])
  const [selectedSize, setSelectedSize] = useState('')
  const [selectedColor, setSelectedColor] = useState('')

  // Coupons: {storeName: [{code, description, source_url, is_trusted}]}
  const [coupons, setCoupons] = useState({})

  const fileInputRef = useRef(null)

  // ── On mount ──────────────────────────────────────────────────────────────

  useEffect(() => {
    const token = getToken()
    if (token) {
      apiFetch('/api/users/me').then(r => r.json()).then(data => {
        if (data.id) { setUser(data); setMemberships(data.memberships || []) }
        else clearToken()
      }).catch(() => clearToken())
    }
    fetch(`${API_BASE_URL}/api/memberships`)
      .then(r => r.json()).then(d => setAvailableMemberships(d.memberships || [])).catch(() => {})
    setLocationStatus('detecting')
    detectCountryCode().then(({ code, status }) => { setCountryCode(code); setLocationStatus(status) })
  }, [])

  useEffect(() => { if (user) setMemberships(user.memberships || []) }, [user])

  // ── Fetch coupons for all unique stores in results ───────────────────────

  const fetchCoupons = useCallback(async (searchResults) => {
    if (!searchResults || searchResults.length === 0) return
    const stores = [...new Set(searchResults.map(r => r.store).filter(Boolean))]
    if (stores.length === 0) return
    try {
      const resp = await fetch(`${API_BASE_URL}/api/coupons`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stores }),
      })
      if (!resp.ok) return
      const data = await resp.json()
      setCoupons(data.coupons || {})
    } catch { /* silent — coupons are non-critical */ }
  }, [])

  // ── Image search Phase 1: identify ───────────────────────────────────────

  const identifyImage = async () => {
    if (!imageFile) return
    setImagePhase('identifying')
    setErrorMessage('')
    setIdentifiedAs(null)
    setProductType(null)
    setResults([])

    const formData = new FormData()
    formData.append('file', imageFile)
    formData.append('country_code', countryCode || 'us')

    try {
      const resp = await fetch(`${API_BASE_URL}/api/search/identify`, { method: 'POST', body: formData })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Identification failed')
      setIdentifiedAs(data.identified_as)
      setSearchTerm(data.search_term || data.identified_as || '')
      setProductType(data.product_type)
      setAvailableSizes(data.sizes || [])
      setAvailableColors(data.colors || [])
      setSelectedSize('')
      setSelectedColor('')
      setImagePhase('filters')
    } catch (err) {
      setErrorMessage(err.message)
      setImagePhase('idle')
    }
  }

  // ── Image search Phase 2: search with filters ─────────────────────────────

  const searchWithFilters = async () => {
    setImagePhase('searching')
    setErrorMessage('')
    setResults([])
    setCoupons({})

    const formData = new FormData()
    formData.append('file', imageFile)
    formData.append('country_code', countryCode || 'us')
    formData.append('memberships', memberships.join(','))
    formData.append('size', selectedSize)
    formData.append('color', selectedColor)

    try {
      const resp = await fetch(`${API_BASE_URL}/api/search/image`, { method: 'POST', body: formData })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Search failed')
      const newResults = data.results || []
      setResults(newResults)
      setImagePhase('results')
      fetchCoupons(newResults)
    } catch (err) {
      setErrorMessage(err.message)
      setImagePhase('filters') // go back to filters on error
    }
  }

  // ── Text search ───────────────────────────────────────────────────────────

  const runTextSearch = async () => {
    if (!query.trim()) return
    setSearchStatus('loading')
    setErrorMessage('')
    setResults([])
    setCoupons({})

    const formData = new FormData()
    formData.append('query', query)
    formData.append('country_code', countryCode || 'us')
    formData.append('memberships', memberships.join(','))
    formData.append('size', selectedSize)
    formData.append('color', selectedColor)

    try {
      const resp = await fetch(`${API_BASE_URL}/api/search/text`, { method: 'POST', body: formData })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || `Request failed (${resp.status})`)
      const newResults = data.results || []
      setResults(newResults)
      setSearchStatus('success')
      fetchCoupons(newResults)
    } catch (err) {
      setErrorMessage(err.message)
      setSearchStatus('error')
    }
  }

  // ── Reset image state when new file chosen ────────────────────────────────

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    setImagePreviewUrl(URL.createObjectURL(file))
    setImagePhase('idle')
    setIdentifiedAs(null)
    setSearchTerm('')
    setProductType(null)
    setResults([])
    setSelectedSize('')
    setSelectedColor('')
    setErrorMessage('')
  }

  const resetImageSearch = () => {
    setImageFile(null)
    setImagePreviewUrl(null)
    setImagePhase('idle')
    setIdentifiedAs(null)
    setProductType(null)
    setResults([])
    setSelectedSize('')
    setSelectedColor('')
    setErrorMessage('')
    setCoupons({})
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const logout = () => { clearToken(); setUser(null); setMemberships([]); setShowProfile(false) }

  // ── Derived UI state ──────────────────────────────────────────────────────

  const isImageBusy = imagePhase === 'identifying' || imagePhase === 'searching'
  const textSuccess = searchStatus === 'success'
  const textError = searchStatus === 'error'

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="page">
      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          onSuccess={u => { setUser(u); setShowAuthModal(false) }}
          availableMemberships={availableMemberships}
        />
      )}

      {/* Header */}
      <div className="header">
        <div>
          <h1>BuyBot — Price Comparison</h1>
          <p className="subtitle">Search by description, or upload a photo of the item.</p>
        </div>
        <div className="header-right">
          <div className="location-status">
            {locationStatus === 'detecting' && <span className="location-badge detecting">📍 Detecting…</span>}
            <label className="country-picker" title="Results and local stores are based on this country">
              📍
              <select value={countryCode || 'us'} onChange={e => setCountryCode(e.target.value)}>
                <option value="il">Israel</option>
                <option value="gb">United Kingdom</option>
                <option value="us">United States</option>
                <option value="de">Germany</option>
                <option value="fr">France</option>
                <option value="es">Spain</option>
                <option value="it">Italy</option>
                <option value="nl">Netherlands</option>
                <option value="au">Australia</option>
              </select>
            </label>
          </div>
          {user
            ? <button className="profile-toggle" onClick={() => setShowProfile(v => !v)}>👤 {user.email.split('@')[0]}</button>
            : <button className="sign-in-btn" onClick={() => setShowAuthModal(true)}>Sign in</button>
          }
        </div>
      </div>

      {showProfile && user && (
        <ProfilePanel user={user} availableMemberships={availableMemberships}
          onUpdate={setUser} onLogout={logout} />
      )}

      {/* Mode toggle */}
      <div className="mode-toggle">
        <button className={mode === 'text' ? 'active' : ''} onClick={() => setMode('text')}>Text search</button>
        <button className={mode === 'image' ? 'active' : ''} onClick={() => setMode('image')}>Photo search</button>
      </div>

      {/* ── TEXT SEARCH ── */}
      {mode === 'text' && (
        <>
          <div className="search-box">
            <input
              type="text"
              placeholder='e.g. "beige button-down shirt"'
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runTextSearch()}
            />
          </div>
          {!user && availableMemberships.length > 0 && (
            <MembershipSelector memberships={memberships} available={availableMemberships} onChange={setMemberships} />
          )}
          <button className="search-button" onClick={runTextSearch} disabled={searchStatus === 'loading'}>
            {searchStatus === 'loading' ? 'Searching…' : 'Search'}
          </button>
          {textError && <p className="error">{errorMessage}</p>}
          {textSuccess && results.length === 0 && <p className="empty">No matches found.</p>}
          {textSuccess && (
            <StoreLinks query={query} countryCode={countryCode} memberships={memberships}
              size={selectedSize} color={selectedColor} />
          )}
        </>
      )}

      {/* ── IMAGE SEARCH — two-phase ── */}
      {mode === 'image' && (
        <>
          {/* Phase idle / identifying: show upload area */}
          {(imagePhase === 'idle' || imagePhase === 'identifying') && (
            <div className="phase-block">
              <div className="phase-label">
                <span className="phase-number">1</span>
                <span>Upload a photo — we'll identify the item and show available sizes and colors</span>
              </div>
              <div className="search-box">
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} />
                {imagePreviewUrl && <img src={imagePreviewUrl} alt="preview" className="image-preview" />}
              </div>
              <button
                className="search-button"
                onClick={identifyImage}
                disabled={!imageFile || imagePhase === 'identifying'}
              >
                {imagePhase === 'identifying' ? 'Identifying…' : 'Identify'}
              </button>
              {errorMessage && <p className="error">{errorMessage}</p>}
            </div>
          )}

          {/* Phase filters / searching / results: show identified item + filters */}
          {(imagePhase === 'filters' || imagePhase === 'searching' || imagePhase === 'results') && (
            <>
              {/* Identified item banner */}
              <div className="identified-banner">
                <div className="identified-banner-left">
                  {imagePreviewUrl && <img src={imagePreviewUrl} alt="uploaded" className="identified-thumb" />}
                  <div>
                    <p className="identified-label">Identified as</p>
                    <p className="identified-name">{identifiedAs || 'Unknown item'}</p>
                  </div>
                </div>
                <button className="identified-reset" onClick={resetImageSearch}>
                  ✕ New image
                </button>
              </div>

              {/* Phase 2 block */}
              <div className="phase-block">
                <div className="phase-label">
                  <span className="phase-number">2</span>
                  <span>Select size and color, then search</span>
                </div>

                <SizeColorFilters
                  productType={productType}
                  sizes={availableSizes}
                  colors={availableColors}
                  selectedSize={selectedSize}
                  selectedColor={selectedColor}
                  onSizeChange={setSelectedSize}
                  onColorChange={setSelectedColor}
                />

                {!user && availableMemberships.length > 0 && (
                  <MembershipSelector memberships={memberships} available={availableMemberships} onChange={setMemberships} />
                )}

                <button
                  className="search-button"
                  onClick={searchWithFilters}
                  disabled={imagePhase === 'searching'}
                >
                  {imagePhase === 'searching' ? 'Searching…' : 'Get stores'}
                </button>

                {errorMessage && <p className="error">{errorMessage}</p>}
              </div>

              {/* Results */}
              {imagePhase === 'results' && results.length === 0 && <p className="empty">No matches found.</p>}
              {imagePhase === 'results' && (
                <StoreLinks query={searchTerm || identifiedAs} countryCode={countryCode} memberships={memberships}
                  size={selectedSize} color={selectedColor} />
              )}
            </>
          )}
        </>
      )}

      {/* Results table — shared between text and image */}
      {results.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>Image</th><th>Name</th><th>Store</th><th>Price</th><th></th>
            </tr>
          </thead>
          <tbody>
            {results.map(r => (
              <tr key={r.id} className={r.membership_id ? 'has-discount' : ''}>
                <td>{r.image_url && <img src={r.image_url} alt={r.name} className="thumb" />}</td>
                <td>{r.name}</td>
                <td>
                  {r.store}
                  {r.membership_name && (
                    <span className="membership-tag" title={r.membership_description}>{r.membership_name}</span>
                  )}
                  <StoreCoupons storeName={r.store} coupons={coupons[r.store]} />
                </td>
                <PriceCell price={r.price} currency={r.currency}
                  discountedPrice={r.discounted_price} discountPct={r.discount_pct}
                  membershipName={r.membership_name} clubPrice={r.club_price} salePrice={r.sale_price} />
                <td>
                  <a href={buildProductUrl(r.url, r.store, selectedColor)}
                    target="_blank" rel="noreferrer">View</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
