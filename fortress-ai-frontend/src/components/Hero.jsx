import { useState, useEffect } from 'react'

const Hero = ({ systemHealth, setCurrentView }) => {
  const [animatedScore, setAnimatedScore] = useState(0)
  const [animatedIncidents, setAnimatedIncidents] = useState(0)

  useEffect(() => {
    if (systemHealth) {
      // Animate health score
      const scoreInterval = setInterval(() => {
        setAnimatedScore(prev => {
          const target = systemHealth.health_score || 88
          if (prev < target) {
            return Math.min(prev + 2, target)
          }
          return target
        })
      }, 50)

      // Animate incidents
      const incidentInterval = setInterval(() => {
        setAnimatedIncidents(prev => {
          const target = systemHealth.recent_incidents || 2
          if (prev < target) {
            return prev + 1
          }
          return target
        })
      }, 200)

      return () => {
        clearInterval(scoreInterval)
        clearInterval(incidentInterval)
      }
    }
  }, [systemHealth])

  const getStatusColor = (status) => {
    if (status === 'healthy') return 'text-green-400'
    if (status === 'degraded') return 'text-yellow-400'
    if (status === 'demo') return 'text-blue-400'
    return 'text-red-400'
  }

  const getStatusText = (status) => {
    if (status === 'demo') return 'DEMO MODE'
    return status?.toUpperCase() || 'UNKNOWN'
  }

  return (
    <main className="pt-20 min-h-screen flex items-center">
      <div className="max-w-7xl mx-auto px-6 py-20">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left Column - Main Content */}
          <div className="space-y-8">
            <div className="space-y-2">
              <p className="text-sm text-gray-400 tracking-wider uppercase">
                AI/ML SECURITY — DEFENSE PLATFORM
              </p>
              <h1 className="text-6xl lg:text-7xl font-light leading-tight">
                Fortress
                <span className="italic font-light text-gray-300 block">AI</span>
              </h1>
            </div>

            <div className="space-y-6">
              <h2 className="text-2xl font-light text-gray-300">
                Building <span className="italic">Intelligence</span> at Scale
              </h2>
              
              <p className="text-lg text-gray-400 leading-relaxed max-w-lg">
                Zero-trust AI agent security platform with real-time threat detection, 
                behavioral analysis, and automated quarantine systems that protect 
                against prompt injection and data exfiltration.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <button 
                onClick={() => setCurrentView('dashboard')}
                className="px-8 py-3 bg-white text-black font-medium tracking-wide hover:bg-gray-200 transition-colors"
              >
                VIEW DASHBOARD →
              </button>
              <button 
                onClick={() => setCurrentView('test')}
                className="px-8 py-3 border border-gray-600 hover:border-white transition-colors"
              >
                RUN TESTS →
              </button>
            </div>
          </div>

          {/* Right Column - Metrics */}
          <div className="space-y-12">
            {/* System Status */}
            <div className="space-y-4">
              <div className="text-right">
                <div className="text-5xl font-light">
                  {animatedScore}
                  <span className="text-2xl text-gray-400">%</span>
                </div>
                <div className="text-sm text-gray-400 tracking-wider uppercase">
                  SECURITY HEALTH SCORE
                </div>
                <div className="text-xs text-gray-500">
                  Real-time threat assessment
                </div>
              </div>
            </div>

            {/* Status Indicator */}
            <div className="space-y-4">
              <div className="text-right">
                <div className={`text-3xl font-light ${getStatusColor(systemHealth?.status)}`}>
                  {getStatusText(systemHealth?.status)}
                </div>
                <div className="text-sm text-gray-400 tracking-wider uppercase">
                  SYSTEM STATUS
                </div>
                <div className="text-xs text-gray-500">
                  Multi-layer defense active
                </div>
              </div>
            </div>

            {/* Incidents */}
            <div className="space-y-4">
              <div className="text-right">
                <div className="text-4xl font-light">
                  {animatedIncidents}
                  <span className="text-xl text-gray-400">x</span>
                </div>
                <div className="text-sm text-gray-400 tracking-wider uppercase">
                  THREATS BLOCKED
                </div>
                <div className="text-xs text-gray-500">
                  Last 24 hours
                </div>
              </div>
            </div>

            {/* Connect Section */}
            <div className="pt-8 border-t border-gray-800">
              <div className="text-right space-y-4">
                <p className="text-sm text-gray-400 tracking-wider uppercase">
                  CONNECT
                </p>
                <div className="flex justify-end space-x-4">
                  <a href="https://github.com" className="p-2 hover:bg-gray-800 rounded transition-colors">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                    </svg>
                  </a>
                  <a href="https://linkedin.com" className="p-2 hover:bg-gray-800 rounded transition-colors">
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                  </a>
                  <a href="mailto:contact@fortressai.com" className="p-2 hover:bg-gray-800 rounded transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </a>
                </div>
              </div>

              <div className="text-right mt-8 space-y-2">
                <p className="text-sm text-gray-400 tracking-wider uppercase">
                  STATUS
                </p>
                <div className="flex items-center justify-end space-x-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-sm text-gray-300">Open to opportunities</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}

export default Hero