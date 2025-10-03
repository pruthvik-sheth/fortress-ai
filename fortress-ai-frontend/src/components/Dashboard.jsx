import { useState, useEffect } from 'react'

const Dashboard = ({ systemHealth, refreshHealth }) => {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchIncidents()
  }, [])

  const fetchIncidents = async () => {
    try {
      const response = await fetch('http://localhost:9000/incidents')
      const data = await response.json()
      setIncidents(data.incidents || [])
    } catch (error) {
      console.log('Using demo incident data')
      setIncidents([
        {
          ts: Date.now() / 1000 - 300,
          agent_id: 'agent-007',
          score: 100,
          action: 'QUARANTINE',
          reasons: ['secrets_detected: api_key'],
          url: 'https://example.org/upload'
        },
        {
          ts: Date.now() / 1000 - 600,
          agent_id: 'agent-003',
          score: 70,
          action: 'BLOCK',
          reasons: ['denylisted_domain: pastebin.com'],
          url: 'https://pastebin.com/evil'
        },
        {
          ts: Date.now() / 1000 - 900,
          agent_id: 'agent-001',
          score: 85,
          action: 'BLOCK',
          reasons: ['instruction_override'],
          url: 'N/A'
        }
      ])
    }
  }

  const generateReport = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:9000/compliance/generate', {
        method: 'POST'
      })
      const data = await response.json()
      
      // Create and download the HTML report
      const blob = new Blob([data.html], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'fortress-ai-evidence-pack.html'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to generate report:', error)
    }
    setLoading(false)
  }

  const formatTime = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleTimeString()
  }

  const getActionColor = (action) => {
    switch (action) {
      case 'QUARANTINE': return 'text-red-400 bg-red-400/10'
      case 'BLOCK': return 'text-yellow-400 bg-yellow-400/10'
      case 'ALLOW+WATCH': return 'text-blue-400 bg-blue-400/10'
      default: return 'text-gray-400 bg-gray-400/10'
    }
  }

  const getHealthColor = (score) => {
    if (score >= 90) return 'text-green-400'
    if (score >= 70) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <main className="pt-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl font-light mb-4">Security Dashboard</h1>
          <p className="text-gray-400">Real-time monitoring and threat intelligence</p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div className="bg-gray-900/50 border border-gray-800 p-6 rounded-lg">
            <div className="text-3xl font-light mb-2">
              <span className={getHealthColor(systemHealth?.health_score || 88)}>
                {systemHealth?.health_score || 88}%
              </span>
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wider">Health Score</div>
            <div className="text-xs text-gray-500 mt-1">Multi-layer defense</div>
          </div>

          <div className="bg-gray-900/50 border border-gray-800 p-6 rounded-lg">
            <div className="text-3xl font-light mb-2 text-red-400">
              {systemHealth?.quarantined_agents || 1}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wider">Quarantined</div>
            <div className="text-xs text-gray-500 mt-1">Compromised agents</div>
          </div>

          <div className="bg-gray-900/50 border border-gray-800 p-6 rounded-lg">
            <div className="text-3xl font-light mb-2 text-yellow-400">
              {systemHealth?.recent_incidents || 2}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wider">Incidents</div>
            <div className="text-xs text-gray-500 mt-1">Last 24 hours</div>
          </div>

          <div className="bg-gray-900/50 border border-gray-800 p-6 rounded-lg">
            <div className="text-3xl font-light mb-2 text-green-400">
              {systemHealth?.status === 'healthy' ? '✓' : systemHealth?.status === 'demo' ? '◉' : '⚠'}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wider">Status</div>
            <div className="text-xs text-gray-500 mt-1">
              {systemHealth?.status === 'demo' ? 'Demo mode' : systemHealth?.status || 'Unknown'}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-4 mb-8">
          <button
            onClick={refreshHealth}
            className="px-6 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded transition-colors"
          >
            Refresh Status
          </button>
          <button
            onClick={generateReport}
            disabled={loading}
            className="px-6 py-2 bg-white text-black hover:bg-gray-200 rounded transition-colors disabled:opacity-50"
          >
            {loading ? 'Generating...' : 'Generate Report'}
          </button>
        </div>

        {/* Incidents Table */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
          <div className="p-6 border-b border-gray-800">
            <h2 className="text-xl font-light">Recent Security Incidents</h2>
            <p className="text-gray-400 text-sm mt-1">Real-time threat detection and response</p>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-800/50">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Time</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Agent ID</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Action</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Score</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Reason</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">URL</th>
                </tr>
              </thead>
              <tbody>
                {incidents.length > 0 ? incidents.slice(0, 10).map((incident, index) => (
                  <tr key={index} className="border-b border-gray-800 hover:bg-gray-800/30">
                    <td className="p-4 text-sm text-gray-300">
                      {formatTime(incident.ts)}
                    </td>
                    <td className="p-4 text-sm font-mono text-gray-300">
                      {incident.agent_id}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getActionColor(incident.action)}`}>
                        {incident.action}
                      </span>
                    </td>
                    <td className="p-4 text-sm text-gray-300">
                      {incident.score}
                    </td>
                    <td className="p-4 text-sm text-gray-400 max-w-xs truncate">
                      {incident.reasons?.join(', ') || 'N/A'}
                    </td>
                    <td className="p-4 text-sm text-gray-400 max-w-xs truncate font-mono">
                      {incident.url || 'N/A'}
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="6" className="p-8 text-center text-gray-400">
                      No incidents recorded
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* System Architecture */}
        <div className="mt-12 bg-gray-900/50 border border-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-light mb-6">System Architecture</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center p-6 border border-gray-700 rounded-lg">
              <div className="text-3xl mb-3">🛡️</div>
              <h3 className="font-medium mb-2">Ingress Broker</h3>
              <p className="text-sm text-gray-400">Port 8001 • Front door security</p>
              <p className="text-xs text-gray-500 mt-2">API validation, firewall, JWT tokens</p>
            </div>
            <div className="text-center p-6 border border-gray-700 rounded-lg">
              <div className="text-3xl mb-3">🤖</div>
              <h3 className="font-medium mb-2">AI Agent</h3>
              <p className="text-sm text-gray-400">Port 7000 • Isolated processing</p>
              <p className="text-xs text-gray-500 mt-2">Claude AI, no direct internet access</p>
            </div>
            <div className="text-center p-6 border border-gray-700 rounded-lg">
              <div className="text-3xl mb-3">🚪</div>
              <h3 className="font-medium mb-2">Egress Gateway</h3>
              <p className="text-sm text-gray-400">Port 9000 • Outbound monitoring</p>
              <p className="text-xs text-gray-500 mt-2">Threat scoring, auto-quarantine</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}

export default Dashboard