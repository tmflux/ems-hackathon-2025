// src/main.jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app'   // Capital A
import 'bootstrap/dist/css/bootstrap.min.css'  // ✅ Optional if CDN not used

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
