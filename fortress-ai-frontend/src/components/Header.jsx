import { useState } from 'react'

const Header = ({ currentView, setCurrentView }) => {
  const [isDarkMode, setIsDarkMode] = useState(true)

  const navItems = [
    { id: 'home', label: 'HOME' },
    { id: 'dashboard', label: 'DASHBOARD' },
    { id: 'test', label: 'TEST SUITE' },
    { id: 'docs', label: 'DOCS' }
  ]

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-black/80 backdrop-blur-sm border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div 
            className="text-xl font-light cursor-pointer hover:text-gray-300 transition-colors"
            onClick={() => setCurrentView('home')}
          >
            FORTRESS AI
          </div>

          {/* Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setCurrentView(item.id)}
                className={`text-sm font-light tracking-wider transition-colors ${
                  currentView === item.id 
                    ? 'text-white' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {/* Theme Toggle */}
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <svg 
              className="w-5 h-5" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              {isDarkMode ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              )}
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header