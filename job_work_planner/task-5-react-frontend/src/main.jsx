/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: main.jsx
 * 
 * 1) Purpose: Frontend core logic.
 * 2) Roadmap Connection: Contributes to the Stage 2 (v1.5) UI/UX requirements. 
 *    Implements the "Safety Orange" aesthetics, JetBrains Mono precision typography, 
 *    and responsive data visualization critical for shop-floor dashboards.
 */

import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import './index.css'
import './lib/amplify'
import App from './App'
import { CONFIG } from './config'
import { AuthProvider } from './context/AuthContext'

import ErrorBoundary from './components/common/ErrorBoundary'

const appTree = (
  <ErrorBoundary fullscreen>
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AuthProvider>
        <Toaster position="top-right" />
        <App />
      </AuthProvider>
    </BrowserRouter>
  </ErrorBoundary>
)

const rootElement = document.getElementById('root')

if (rootElement) {
  try {
    const root = ReactDOM.createRoot(rootElement)
    root.render(
      CONFIG.IS_DEV ? (
        appTree
      ) : (
        <React.StrictMode>{appTree}</React.StrictMode>
      )
    )
  } catch (error) {
    console.error('CRITICAL: React Mount Failure', error)
    rootElement.innerHTML = `
      <div style="font-family: inherit; padding: 40px; text-align: center; background: #0f172a; min-height: 100vh; color: #f8fafc; display: flex; flex-direction: column; justify-content: center; align-items: center;">
        <div style="background: #ef4444; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 900; margin-bottom: 20px;">!</div>
        <h1 style="font-size: 24px; font-weight: 900; margin-bottom: 10px; letter-spacing: -1px;">SYSTEM INITIALIZING</h1>
        <p style="color: #94a3b8; max-width: 400px; line-height: 1.6;">The dashboard is performing a core integrity check. If this message persists, please clear your browser cache and refresh.</p>
        <button onclick="window.location.reload()" style="margin-top: 20px; background: #f97316; color: #0f172a; border: none; padding: 12px 24px; font-weight: 900; border-radius: 12px; cursor: pointer; text-transform: uppercase; letter-spacing: 1px;">Reload Console</button>
      </div>
    `
  }
}
