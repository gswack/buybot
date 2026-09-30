import { useState, useRef, useEffect } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Reverse-geocode coordinates to a country code using the free bigdatacloud API
async function detectCountryCode() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve('us')
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const resp = await fetch(
            `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${coords.latitude}&longitude=${coords.longitude}&localityLanguage=en`
          )
          const data = await resp.json()
          resolve((data.countryCode || 'us').toLowerCase())
        } catch {
          resolve('us')
        }
      },
      () => resolve('us'), // permission denied or unavailable → default to us
      { timeout: 5000 }
    )
  })
}

function MembershipSelector({ memberships, available, onChange }) {
  return (
    <div className="memberships">
      <p className="memberships-label">Your memberships</p>
      <div className="memberships-list">
        {available.map((p) => {
          const checked = memberships.includes(p.id)
          return (
            <label key={p.id} className={`membership-chip ${checked ? 'active' : ''}`} title={p.description}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() =>
                  onChange(
                    checked
                      ? memberships.filter((m) => m !== p.id)
                      : [...memberships, p.id]
                  )
                }
              />
              {p.name}
              {p.discount_pct > 0 && (
                <span className="discount-badge">{p.discount_pct}% off</span>
              )}
            </label>
          )
        })}
      </div>
    </div>
  )
}

function PriceCell({ price, currency, discountedPrice, discountPct, membershipName, clubPrice, salePrice }) {
  if (price == null && clubPrice == null && salePrice == null) return <td>—</td>

  // Jack Kuba scraped results: show regular + club price side by side
  if (clubPrice != null && discountedPrice == null) {
    return (
      <td>
        <span className="price-with-discount">
          <span className="price-original">{price} {currency}</span>
          <span className="price-discounted">{clubPrice} {currency}</span>
          <span className="discount-tag">מועדון</span>
        </span>
      </td>
    )
  }

  // Sale price (no club membership involved)
  if (salePrice != null && salePrice !== price) {
    return (
      <td>
        <span className="price-with-discount">
          <span className="price-original">{price} {currency}</span>
          <span className="price-discounted">{salePrice} {currency}</span>
          <span className="discount-tag">מבצע</span>
        </span>
      </td>
    )
  }

  // Membership discount applied by backend (non-Jack-Kuba stores)
  const hasDiscount = discountedPrice != null && discountPct > 0
  if (hasDiscount) {
    return (
      <td>
        <span className="price-with-discount">
          <span className="price-original">{price} {currency}</span>
          <span className="price-discounted">{discountedPrice} {currency}</span>
          <span className="discount-tag" title={membershipName}>-{discountPct}%</span>
        </span>
      </td>
    )
  }

  return <td><span>{price} {currency}</span></td>
}

// Stores that don't appear in Google Shopping — shown as direct search links.
// Keyed by country code. Each entry has a label, search URL template, and
// optional note about membership discounts.
const STORE_LINKS = {
  il: [
    {
      id: 'zara',
      label: 'Zara',
      logo: '🛍️',
      url: (q) => `https://www.zara.com/il/en/search?searchTerm=${encodeURIComponent(q)}`,
      membershipIds: ['zara_member', 'zara_student'],
      membershipNote: 'Your Zara discount applies at checkout',
    },
  ],
  gb: [
    {
      id: 'zara',
      label: 'Zara',
      logo: '🛍️',
      url: (q) => `https://www.zara.com/uk/en/search?searchTerm=${encodeURIComponent(q)}`,
      membershipIds: ['zara_member', 'zara_student'],
      membershipNote: 'Your Zara discount applies at checkout',
    },
  ],
  us: [
    {
      id: 'zara',
      label: 'Zara',
      logo: '🛍️',
      url: (q) => `https://www.zara.com/us/en/search?searchTerm=${encodeURIComponent(q)}`,
      membershipIds: ['zara_member', 'zara_student'],
      membershipNote: 'Your Zara discount applies at checkout',
    },
  ],
}

function StoreLinks({ query, countryCode, memberships }) {
  if (!query) return null
  const country = (countryCode || 'us').toLowerCase()
  const stores = STORE_LINKS[country] || STORE_LINKS['us']

  return (
    <div className="store-links">
      <p className="store-links-label">
        These stores don't list on Google Shopping — search them directly:
      </p>
      <div className="store-links-list">
        {stores.map((store) => {
          const hasMembership = memberships?.some((m) => store.membershipIds.includes(m))
          return (
            <a
              key={store.id}
              href={store.url(query)}
              target="_blank"
              rel="noreferrer"
              className={`store-link-card ${hasMembership ? 'has-membership' : ''}`}
            >
              <span className="store-link-logo">{store.logo}</span>
              <span className="store-link-name">{store.label}</span>
              {hasMembership && (
                <span className="store-link-membership-note">{store.membershipNote}</span>
              )}
              <span className="store-link-arrow">→</span>
            </a>
          )
        })}
      </div>
    </div>
  )
}

function LocationBadge({ countryCode }) {  if (!countryCode) return null
  return (
    <span className="location-badge" title="Results localised to your region">
      📍 {countryCode.toUpperCase()}
    </span>
  )
}

export default function App() {
  const [mode, setMode] = useState('text')
  const [query, setQuery] = useState('')
  const [imageFile, setImageFile] = useState(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null)
  const [results, setResults] = useState([])
  const [status, setStatus] = useState('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [identifiedAs, setIdentifiedAs] = useState(null)
  const [countryCode, setCountryCode] = useState(null)
  const [locationStatus, setLocationStatus] = useState('idle') // 'idle'|'detecting'|'found'|'denied'
  const [memberships, setMemberships] = useState([])
  const [availableMemberships, setAvailableMemberships] = useState([])
  const fileInputRef = useRef(null)

  // Detect location and fetch membership programs on mount
  useEffect(() => {
    // Fetch available membership programs
    fetch(`${API_BASE_URL}/api/memberships`)
      .then((r) => r.json())
      .then((data) => setAvailableMemberships(data.memberships || []))
      .catch(() => {})

    // Auto-detect location
    setLocationStatus('detecting')
    detectCountryCode().then((code) => {
      setCountryCode(code)
      setLocationStatus(code !== 'us' ? 'found' : 'denied')
    })
  }, [])

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    setImagePreviewUrl(URL.createObjectURL(file))
  }

  const runSearch = async () => {
    setStatus('loading')
    setErrorMessage('')
    setResults([])
    setIdentifiedAs(null)

    const country = countryCode || 'us'
    const membershipStr = memberships.join(',')

    try {
      let response

      if (mode === 'text') {
        if (!query.trim()) throw new Error('Please enter a search query')
        const formData = new FormData()
        formData.append('query', query)
        formData.append('country_code', country)
        formData.append('memberships', membershipStr)
        response = await fetch(`${API_BASE_URL}/api/search/text`, {
          method: 'POST',
          body: formData,
        })
      } else {
        if (!imageFile) throw new Error('Please choose an image first')
        const formData = new FormData()
        formData.append('file', imageFile)
        formData.append('country_code', country)
        formData.append('memberships', membershipStr)
        response = await fetch(`${API_BASE_URL}/api/search/image`, {
          method: 'POST',
          body: formData,
        })
      }

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${response.status})`)
      }

      const data = await response.json()
      setResults(data.results || [])
      setIdentifiedAs(data.identified_as || null)
      setStatus('success')
    } catch (err) {
      setErrorMessage(err.message || 'Something went wrong')
      setStatus('error')
    }
  }

  return (
    <div className="page">
      <div className="header">
        <div>
          <h1>BuyBot — Price Comparison</h1>
          <p className="subtitle">Search by description, or upload a photo of the item.</p>
        </div>
        <div className="location-status">
          {locationStatus === 'detecting' && (
            <span className="location-badge detecting">📍 Detecting location…</span>
          )}
          {locationStatus === 'found' && <LocationBadge countryCode={countryCode} />}
          {locationStatus === 'denied' && (
            <span className="location-badge denied" title="Location unavailable — showing global results">📍 Location unavailable</span>
          )}
        </div>
      </div>

      <div className="mode-toggle">
        <button className={mode === 'text' ? 'active' : ''} onClick={() => setMode('text')}>
          Text search
        </button>
        <button className={mode === 'image' ? 'active' : ''} onClick={() => setMode('image')}>
          Photo search
        </button>
      </div>

      {mode === 'text' ? (
        <div className="search-box">
          <input
            type="text"
            placeholder='e.g. "beige button-down shirt" or a specific item name'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
          />
        </div>
      ) : (
        <div className="search-box">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
          />
          {imagePreviewUrl && (
            <img src={imagePreviewUrl} alt="preview" className="image-preview" />
          )}
        </div>
      )}

      {availableMemberships.length > 0 && (
        <MembershipSelector
          memberships={memberships}
          available={availableMemberships}
          onChange={setMemberships}
        />
      )}

      <button className="search-button" onClick={runSearch} disabled={status === 'loading'}>
        {status === 'loading' ? 'Searching…' : 'Search'}
      </button>

      {status === 'error' && <p className="error">{errorMessage}</p>}

      {status === 'success' && results.length === 0 && (
        <p className="empty">No matches found.</p>
      )}

      {status === 'success' && identifiedAs && (
        <p className="identified-as">
          🔍 Identified as: <strong>{identifiedAs}</strong>
        </p>
      )}

      {status === 'success' && (
        <StoreLinks
          query={identifiedAs || query}
          countryCode={countryCode}
          memberships={memberships}
        />
      )}

      {results.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>Image</th>
              <th>Name</th>
              <th>Store</th>
              <th>Price</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.id} className={r.membership_id ? 'has-discount' : ''}>
                <td>
                  {r.image_url && <img src={r.image_url} alt={r.name} className="thumb" />}
                </td>
                <td>{r.name}</td>
                <td>
                  {r.store}
                  {r.membership_name && (
                    <span className="membership-tag" title={r.membership_description}>
                      {r.membership_name}
                    </span>
                  )}
                </td>
                <PriceCell
                  price={r.price}
                  currency={r.currency}
                  discountedPrice={r.discounted_price}
                  discountPct={r.discount_pct}
                  membershipName={r.membership_name}
                  clubPrice={r.club_price}
                  salePrice={r.sale_price}
                />
                <td>
                  <a href={r.url} target="_blank" rel="noreferrer">View</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
