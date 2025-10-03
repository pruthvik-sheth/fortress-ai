const Footer = () => {
  return (
    <footer className="border-t border-gray-800 bg-black/50">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
          <div className="text-sm text-gray-400">
            © 2024 FortressAI. Built with React + Tailwind CSS.
          </div>
          
          <div className="flex items-center space-x-6 text-sm text-gray-400">
            <span>Zero-Trust AI Security Platform</span>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span>System Operational</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer