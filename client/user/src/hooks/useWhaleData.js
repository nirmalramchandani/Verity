/**
 * Verity — Data Hook
 * Fetches and caches all investor data from the Verity backend
 */
import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let globalCache = null;
let fetchPromise = null;

export function useWhaleData() {
  const [data, setData] = useState(globalCache || {
    investors: [],
    sells: [],
    transactions: [],
  });
  const [loading, setLoading] = useState(!globalCache);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (globalCache) {
      setData(globalCache);
      setLoading(false);
      return;
    }

    setLoading(true);

    if (!fetchPromise) {
      fetchPromise = Promise.all([
        fetch(`${API_BASE}/data/investors?limit=500`),
        fetch(`${API_BASE}/data/sells?limit=500`),
        fetch(`${API_BASE}/data/transactions?limit=500`),
      ])
        .then(async ([invResp, sellResp, txResp]) => {
          if (!invResp.ok || !sellResp.ok || !txResp.ok)
            throw new Error('Failed to connect to Verity backend.');

          const [invData, sellData, txData] = await Promise.all([
            invResp.json(),
            sellResp.json(),
            txResp.json(),
          ]);

          globalCache = {
            investors: invData.data || [],
            sells: sellData.data || [],
            transactions: txData.data || [],
          };
          return globalCache;
        });
    }

    fetchPromise
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
        fetchPromise = null;
      });
  }, []);

  return { ...data, loading, error };
}

/**
 * Fetch a single investor profile by ID
 */
export function useInvestorProfile(id) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE}/data/investors/${encodeURIComponent(id)}`)
      .then((res) => {
        if (!res.ok) throw new Error('Investor not found');
        return res.json();
      })
      .then((data) => {
        setProfile(data.data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  return { profile, loading, error };
}

/**
 * Fetch full portfolio (open lots) for a specific investor
 */
export function useWhalePortfolio(id) {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE}/data/investors/${encodeURIComponent(id)}/portfolio`)
      .then((res) => {
        if (!res.ok) throw new Error('Portfolio not found');
        return res.json();
      })
      .then((data) => {
        setPortfolio(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  return { portfolio, loading, error };
}

/**
 * Invalidate cache and force refetch
 */
export function invalidateWhaleCache() {
  globalCache = null;
  fetchPromise = null;
}
