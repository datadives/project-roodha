import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import './index.css'
import './lib/amplify'
import App from './App'

const appTree = (
  <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    <Toaster position="top-right" />
    <App />
  </BrowserRouter>
)

ReactDOM.createRoot(document.getElementById('root')).render(
  import.meta.env.MODE === 'development' ? appTree : <React.StrictMode>{appTree}</React.StrictMode>,
)
