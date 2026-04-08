import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState('Completing authentication...')

  useEffect(() => {
    const shop = searchParams.get('shop')
    const success = searchParams.get('success')

    console.log('🔙 OAuth callback received', { shop, success })

    if (!shop) {
      setError('Missing shop parameter')
      return
    }

    if (success !== 'true') {
      setError('OAuth authentication failed')
      return
    }

    // Create session on backend
    const BACKEND_URL = 'https://shopiq-production.up.railway.app'
    
    setStatus('Creating session...')

    fetch(`${BACKEND_URL}/auth/session?shop=${shop}`, {
      method: 'POST',
      credentials: 'include',
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`Session creation failed: ${res.status}`)
        }
        return res.json()
      })
      .then(data => {
        console.log('✅ Session created:', data)
        setStatus('Redirecting to dashboard...')
        
        // Small delay to show success message
        setTimeout(() => {
          navigate(`/dashboard?shop=${shop}`)
        }, 500)
      })
      .catch(err => {
        console.error('❌ Session creation error:', err)
        setError(`Failed to create session: ${err.message}`)
      })
  }, [searchParams, navigate])

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">❌</span>
          </div>
          <h2 className="text-xl font-semibold text-slate-900 mb-2">Authentication Failed</h2>
          <p className="text-sm text-slate-600 mb-6">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="btn-primary"
          >
            Back to Home
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
        <div className="w-16 h-16 bg-brand-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="animate-spin h-8 w-8 text-brand-600" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">Almost there...</h2>
        <p className="text-sm text-slate-600">{status}</p>
      </div>
    </div>
  )
}