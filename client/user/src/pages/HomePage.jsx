import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  BarChart3, 
  Building2, 
  ShieldCheck, 
  Layers, 
  ArrowRight, 
  Activity, 
  Cpu, 
  Target, 
  Search,
  Database,
  TrendingUp
} from 'lucide-react';

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="home-container">
      {/* Institutional Hero Section */}
      <section className="home-hero">
        <div className="hero-badge">
          <span>INSTITUTIONAL CAPITAL MARKETS PLATFORM</span>
        </div>
        
        <h1 className="hero-title">
          Institutional Market Flow & <span className="gradient-text">Quantitative Signal Analytics</span>
        </h1>
        
        <p className="hero-subtitle">
          Enterprise intelligence engine for real-time bulk and block deal reconciliation, 
          corporate action split-normalization, institutional track record analysis, and multi-factor quantitative strategies.
        </p>

        {/* Action Buttons */}
        <div className="hero-actions">
          <button 
            className="btn-primary-large" 
            onClick={() => navigate('/dashboard')}
          >
            <BarChart3 size={18} />
            <span>Open Market Terminal</span>
            <ArrowRight size={16} />
          </button>
          
          <button 
            className="btn-secondary-large" 
            onClick={() => navigate('/signals')}
          >
            <Target size={18} />
            <span>Quantitative Signal Center</span>
          </button>
        </div>
      </section>

      {/* Core Platform Architecture */}
      <section className="instructions-section">
        <div className="section-header">
          <h2>Core System Architecture</h2>
          <p>End-to-end pipeline processing raw exchange transaction feeds into quantitative research metrics</p>
        </div>

        <div className="instructions-grid">
          <div className="instruction-card">
            <div className="card-icon blue">
              <Database size={22} />
            </div>
            <h3>1. Stream Ingestion & Corporate Actions</h3>
            <p>
              Real-time ingestion of exchange bulk and block deals with automatic reconciliation of stock splits, 
              bonus issues, and face-value adjustments.
            </p>
          </div>

          <div className="instruction-card">
            <div className="card-icon emerald">
              <Building2 size={22} />
            </div>
            <h3>2. Institutional Investor Profiling</h3>
            <p>
              Algorithmic calculation of investor hit-ratios, historical win-loss distributions, 
              and total cumulative capital deployment across 20,000+ market participants.
            </p>
          </div>

          <div className="instruction-card">
            <div className="card-icon violet">
              <Cpu size={22} />
            </div>
            <h3>3. Multi-Factor Strategy Engine</h3>
            <p>
              Quantitative scoring combining institutional co-investment clustering, weighted cost-basis 
              expansion, and relative volume intensity metrics.
            </p>
          </div>

          <div className="instruction-card">
            <div className="card-icon amber">
              <ShieldCheck size={22} />
            </div>
            <h3>4. Risk & Signal Dispatch</h3>
            <p>
              Systematic exit detection and real-time multi-channel notification dispatch for high-conviction 
              institutional capital movements.
            </p>
          </div>
        </div>
      </section>

      {/* Executive Modules Hub */}
      <section className="navigation-hub">
        <div className="section-header">
          <h2>Terminal Analytics Modules</h2>
          <p>Select a module to access specialized analytical workflows</p>
        </div>

        <div className="hub-grid">
          <div className="hub-card" onClick={() => navigate('/dashboard')}>
            <div className="hub-card-header">
              <BarChart3 className="hub-icon blue" size={20} />
              <span className="hub-tag">Executive</span>
            </div>
            <h3>Market Dashboard</h3>
            <p>Macro capital flow, portfolio PnL trends, top institutional allocators, and sector concentration metrics.</p>
            <div className="hub-footer">
              <span>Access Terminal</span>
              <ArrowRight size={15} />
            </div>
          </div>

          <div className="hub-card" onClick={() => navigate('/whales')}>
            <div className="hub-card-header">
              <Building2 className="hub-icon emerald" size={20} />
              <span className="hub-tag">Database</span>
            </div>
            <h3>Institutional Directory</h3>
            <p>Filter and analyze 20,000+ institutional holders, funds, and promoters by conviction index and track record.</p>
            <div className="hub-footer">
              <span>View Directory</span>
              <ArrowRight size={15} />
            </div>
          </div>

          <div className="hub-card" onClick={() => navigate('/signals')}>
            <div className="hub-card-header">
              <Target className="hub-icon violet" size={20} />
              <span className="hub-tag">Quantitative</span>
            </div>
            <h3>Quantitative Signals</h3>
            <p>High-conviction transaction signals scored across herding, cost-basis, and volume intensity metrics.</p>
            <div className="hub-footer">
              <span>View Signals</span>
              <ArrowRight size={15} />
            </div>
          </div>

          <div className="hub-card" onClick={() => navigate('/herd')}>
            <div className="hub-card-header">
              <Layers className="hub-icon amber" size={20} />
              <span className="hub-tag">Clustering</span>
            </div>
            <h3>Co-Investment Radar</h3>
            <p>Identify institutional clustering where multiple independent entities accumulate positions within rolling windows.</p>
            <div className="hub-footer">
              <span>View Clustering</span>
              <ArrowRight size={15} />
            </div>
          </div>
        </div>
      </section>

      {/* Terminal Footer Callout */}
      <div className="home-banner">
        <div className="banner-content">
          <h3>Access Verity Executive Research Terminal</h3>
          <p>Inspect institutional portfolios, split-adjusted transactions, and factor breakdown models.</p>
        </div>
        <button className="btn-primary-large" onClick={() => navigate('/dashboard')}>
          <span>Enter Terminal</span>
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
