import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import HomePage from './pages/HomePage';
import CommandCenter from './pages/CommandCenter';
import WhaleScanner from './pages/WhaleScanner';
import WhaleProfile from './pages/WhaleProfile';
import HerdRadar from './pages/HerdRadar';
import AlphaTable from './pages/AlphaTable';
import LiveActivity from './pages/LiveActivity';
import SignalCommandCenter from './pages/SignalCommandCenter';
import './index.css';

function App() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="mobile-header">
          <h1>VERITY</h1>
          <button 
            className="mobile-menu-btn"
            onClick={() => setIsMobileMenuOpen(true)}
          >
            <Menu size={24} />
          </button>
        </header>

        <Sidebar 
          isOpen={isMobileMenuOpen} 
          onClose={() => setIsMobileMenuOpen(false)} 
        />
        <main className="main-viewport">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<CommandCenter />} />
            <Route path="/whales" element={<WhaleScanner />} />
            <Route path="/whale/:id" element={<WhaleProfile />} />
            <Route path="/herd" element={<HerdRadar />} />
            <Route path="/alpha" element={<AlphaTable />} />
            <Route path="/activity" element={<LiveActivity />} />
            <Route path="/signals" element={<SignalCommandCenter />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
