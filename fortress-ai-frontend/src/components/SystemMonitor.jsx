import { useState } from 'react'

const SystemMonitor = ({ systemHealth, incidents, connectionStatus, refreshData }) => {
  const [generatingReport, setGeneratingReport] = useState(false)

  const generateComplianceReport = async () => {
    if (connectionStatus !== 'connected') {
      alert('System must be online to generate reports')
      return
    }

    setGeneratingReport(true)
    try {
      const response = await fetch('http://localhost:9000/compliance/generate', {
        method: 'POST'
      })
      
      if (response.ok) {
        const data = await response.json()
        
        // Create and download the HTML report
        const blob = new Blob([data.html], { type: 'text/html' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'fortress-ai-compliance-report.html'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      } else {
        alert('Failed to generate report')
      }
    } catch (error) {
      alert('Error generating report: ' + error.message)
    }
    setGeneratingReport(false)
  }

  const formatTime = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString()
  }

  const getActionColor = (action) => {
    switch (action) {
      case 'QUARANTINE': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'BLOCK': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'ALLOW+WATCH': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  const getHealthColor = (score) => {
    if (score >= 90) return 'text-green-400'
    if (score >= 70) return 'text-yellow-400'
    return 'text-red-400'
  }

  if (connectionStatus === 'offline') {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">🔌</div>
        <h2 className="text-2xl font-bold mb-2">System Offline</h2>
        <p className="text-gray-400 mb-6">
          Start your FortressAI backend to view system metrics
        </p>
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 max-w-md mx-auto">
          <p className="text-sm text-gray-300 mb-2">To start the system:</p>
          <code className="text-xs bg-black px-2 py-1 rounded text-green-400">
            docker-compose up --build
          </code>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* System Health Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Health Score</span>
            <span className="text-2xl">💚</span>
          </div>
          <div className={`text-3xl font-bold ${getHealthColor(systemHealth?.health_score || 0)}`}>
            {systemHealth?.health_score || 0}%
          </div>
          <div className="text-xs text-gray-500 mt-1">System security rating</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Quarantined</span>
            <span className="text-2xl">⚠️</span>
          </div>
          <div className="text-3xl font-bold text-red-400">
            {systemHealth?.quarantined_agents || 0}
          </div>
          <div className="text-xs text-gray-500 mt-1">Compromised agents</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Incidents</span>
            <span className="text-2xl">🚨</span>
          </div>
          <div className="text-3xl font-bold text-yellow-400">
            {systemHealth?.recent_incidents || 0}
          </div>
          <div className="text-xs text-gray-500 mt-1">Last 24 hours</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Status</span>
            <span className="text-2xl">
              {systemHealth?.status === 'healthy' ? '✅' : 
               systemHealth?.status === 'degraded' ? '⚠️' : '❓'}
            </span>
          </div>
          <div className="text-lg font-bold text-green-400 uppercase">
            {systemHealth?.status || 'Unknown'}
          </div>
          <div className="text-xs text-gray-500 mt-1">System operational</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-4">
        <button
          onClick={refreshData}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
        >
          🔄 Refresh Data
        </button>
        <button
          onClick={generateComplianceReport}
          disabled={generatingReport || connectionStatus !== 'connected'}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generatingReport ? '⏳ Generating...' : '📄 Generate Report'}
        </button>
      </div>

      {/* Recent Incidents */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg">
        <div className="p-6 border-b border-gray-700">
          <h2 className="text-xl font-bold">🚨 Security Incidents</h2>
          <p className="text-gray-400 text-sm">Real-time threat detection log</p>
        </div>
        
        <div className="overflow-x-auto">
          {incidents.length > 0 ? (
            <table className="w-full">
              <thead className="bg-gray-800">
                <tr>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Time</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Agent</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Action</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Score</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">Reason</th>
                  <th className="text-left p-4 text-sm font-medium text-gray-300">URL</th>
                </tr>
              </thead>
              <tbody>
                {incidents.slice(0, 10).map((incident, index) => (
                  <tr key={index} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="p-4 text-sm text-gray-300">
                      {formatTime(incident.ts)}
                    </td>
                    <td className="p-4 text-sm font-mono text-blue-400">
                      {incident.agent_id}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium border ${getActionColor(incident.action)}`}>
                        {incident.action}
                      </span>
                    </td>
                    <td className="p-4 text-sm font-bold">
                      <span className={incident.score >= 80 ? 'text-red-400' : incident.score >= 60 ? 'text-yellow-400' : 'text-green-400'}>
                        {incident.score}
                      </span>
                    </td>
                    <td className="p-4 text-sm text-gray-400 max-w-xs">
                      <div className="truncate">
                        {incident.reasons?.join(', ') || 'N/A'}
                      </div>
                    </td>
                    <td className="p-4 text-sm text-gray-500 max-w-xs">
                      <div className="truncate font-mono">
                        {incident.url || 'N/A'}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-gray-400">
              <div className="text-4xl mb-2">🛡️</div>
              <p>No security incidents detected</p>
              <p className="text-sm text-gray-500">System is secure</p>
            </div>
          )}
        </div>
      </div>

      {/* System Architecture */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-6">🏗️ System Architecture</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center p-6 bg-gray-800 border border-gray-600 rounded-lg">
            <div className="text-4xl mb-3">🛡️</div>
            <h3 className="font-bold mb-2 text-blue-400">Ingress Broker</h3>
            <p className="text-sm text-gray-400 mb-2">Port 8001</p>
            <p className="text-xs text-gray-500">Authentication • Firewall • JWT Tokens</p>
          </div>
          <div className="text-center p-6 bg-gray-800 border border-gray-600 rounded-lg">
            <div className="text-4xl mb-3">🤖</div>
            <h3 className="font-bold mb-2 text-green-400">AI Agent</h3>
            <p className="text-sm text-gray-400 mb-2">Port 7000 (Internal)</p>
            <p className="text-xs text-gray-500">Claude AI • Isolated • No Internet</p>
          </div>
          <div className="text-center p-6 bg-gray-800 border border-gray-600 rounded-lg">
            <div className="text-4xl mb-3">🚪</div>
            <h3 className="font-bold mb-2 text-purple-400">Egress Gateway</h3>
            <p className="text-sm text-gray-400 mb-2">Port 9000</p>
            <p className="text-xs text-gray-500">Monitoring • Scoring • Quarantine</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SystemMonitor