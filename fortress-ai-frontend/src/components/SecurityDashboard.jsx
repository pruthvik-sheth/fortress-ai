import { useState, useEffect } from 'react'
import LiveTesting from './LiveTesting'
import ManualTesting from './ManualTesting'
import SystemMonitor from './SystemMonitor'

const SecurityDashboard = ({ systemHealth, connectionStatus, refreshConnection }) => {
  const [activeTab, setActiveTab] = useState('monitor')
  const [incidents, setIncidents] = useState([])

  useEffect(() => {
    if (connectionStatus === 'connected') {
      fetchIncidents()
    }
  }, [connectionStatus])

  const fetchIncidents = async () => {
    try {
      const response = await fetch('http://localhost:9000/incidents')
      if (response.ok) {
        const data = await response.json()
        setIncidents(data.incidents || [])
      }
    } catch (error) {
      console.log('Could not fetch incidents')
    }
  }

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'text-green-400'
      case 'offline': return 'text-red-400'
      case 'error': return 'text-yellow-400'
      default: return 'text-gray-400'
    }
  }

  const getConnectionStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return 'SYSTEM ONLINE'
      case 'offline': return 'SYSTEM OFFLINE'
      case 'error': return 'CONNECTION ERROR'
      default: return 'CHECKING...'
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h1 className="text-2xl font-bold text-white">🛡️ FortressAI</h1>
              <span className="text-sm text-gray-400">AI Agent Security Platform</span>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className={`text-sm font-medium ${getConnectionStatusColor()}`}>
                {getConnectionStatusText()}
              </div>
              <button
                onClick={refreshConnection}
                className="px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 rounded border border-gray-600 transition-colors"
              >
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="border-b border-gray-800 bg-gray-900/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex space-x-8">
            {[
              { id: 'monitor', label: 'System Monitor', icon: '📊' },
              { id: 'live', label: 'Live Testing', icon: '🧪' },
              { id: 'manual', label: 'Manual Testing', icon: '⚡' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-3 border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-400 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                <span>{tab.icon}</span>
                <span className="font-medium">{tab.label}</span>
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'monitor' && (
          <SystemMonitor 
            systemHealth={systemHealth}
            incidents={incidents}
            connectionStatus={connectionStatus}
            refreshData={() => {
              refreshConnection()
              fetchIncidents()
            }}
          />
        )}
        
        {activeTab === 'live' && (
          <LiveTesting 
            connectionStatus={connectionStatus}
            onTestComplete={fetchIncidents}
          />
        )}
        
        {activeTab === 'manual' && (
          <ManualTesting 
            connectionStatus={connectionStatus}
          />
        )}
      </main>
    </div>
  )
}

export default SecurityDashboard