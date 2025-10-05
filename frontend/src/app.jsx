import React, { useEffect, useState, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Area, AreaChart } from 'recharts'

const apiBase = import.meta.env.VITE_API_BASE ?? "http://localhost:8000"
const WS_BASE = `${apiBase.replace(/^http/, 'ws')}/ws/live`
const RECONNECT_DELAY = 3000
const MAX_HISTORY_POINTS = 100

const rlActionMap = {
  0: { text: 'Balance', color: '#6b7280', bgColor: '#f3f4f6' },
  1: { text: 'Charge Battery', color: '#10b981', bgColor: '#d1fae5' },
  2: { text: 'Discharge Battery', color: '#ef4444', bgColor: '#fee2e2' },
  3: { text: 'Charge EV', color: '#3b82f6', bgColor: '#dbeafe' },
}

const deviceIcons = {
  'batt-01': '🔋',
  'ev-01': '🚗',
  'grid-01': '⚡',
  'load-01': '🏠',
  'pv-01': '☀️',
}

const deviceColors = {
  'batt-01': '#10b981',
  'ev-01': '#3b82f6',
  'grid-01': '#f59e0b',
  'load-01': '#8b5cf6',
  'pv-01': '#eab308',
}

function RLActionDisplay({ rl_action, deviceId }) {
  if (rl_action === undefined || rl_action === null) return null
  
  const action = rlActionMap[rl_action]
  if (!action) return null

  return (
    <div style={{
      background: 'linear-gradient(to right, #f5f3ff, #ede9fe)',
      borderRadius: '12px',
      padding: '16px',
      border: '2px solid #c4b5fd',
      marginBottom: '12px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            background: '#8b5cf6',
            color: 'white',
            borderRadius: '50%',
            padding: '12px',
            fontSize: '24px',
            width: '48px',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            🤖
          </div>
          <div>
            <div style={{
              fontSize: '11px',
              fontWeight: '600',
              color: '#7c3aed',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '4px'
            }}>
              Live RL Agent Decision
            </div>
            <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1f2937' }}>
              {action.text}
            </div>
          </div>
        </div>
        <div style={{
          padding: '8px 16px',
          borderRadius: '20px',
          backgroundColor: action.color,
          color: 'white',
          fontWeight: 'bold',
          fontSize: '14px',
          boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
        }}>
          Action #{rl_action}
        </div>
      </div>
    </div>
  )
}

function DeviceCard({ device, rl_action, advisory }) {
  const numericKeys = Object.keys(device).filter(k => 
    typeof device[k] === 'number' && k !== 'time' && !k.includes('ts') && k !== 'rl_action'
  ).slice(0, 4)
  
  const lastUpdate = device.ts ? new Date(device.ts) : null
  const isStale = lastUpdate && (Date.now() - lastUpdate.getTime() > 10000)
  const critical = (device.soc !== undefined && device.soc < 20) || 
                   (device.ev_soc !== undefined && device.ev_soc < 20)

  const deviceIcon = deviceIcons[device.device_id] || '📊'
  const deviceColor = deviceColors[device.device_id] || '#6b7280'

  const borderColor = isStale ? '#fbbf24' : critical ? '#ef4444' : '#e5e7eb'

  return (
    <div style={{
      backgroundColor: 'white',
      borderRadius: '16px',
      boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
      border: `2px solid ${borderColor}`,
      transition: 'all 0.3s',
      marginBottom: '16px'
    }}>
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ fontSize: '40px' }}>{deviceIcon}</div>
            <div>
              <div style={{
                fontSize: '11px',
                fontWeight: '600',
                color: '#6b7280',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                {device.type || 'Device'}
              </div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1f2937' }}>
                {device.device_id || 'Unknown'}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '11px', color: '#6b7280', marginBottom: '4px' }}>Last Update</div>
            <div style={{ fontSize: '14px', fontWeight: '500', color: '#374151' }}>
              {lastUpdate ? lastUpdate.toLocaleTimeString() : 'N/A'}
            </div>
            {isStale && (
              <span style={{
                display: 'inline-block',
                marginTop: '8px',
                padding: '4px 8px',
                fontSize: '11px',
                fontWeight: '600',
                backgroundColor: '#fef3c7',
                color: '#92400e',
                borderRadius: '12px'
              }}>
                ⚠️ Stale
              </span>
            )}
          </div>
        </div>

        {numericKeys.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
            {numericKeys.map(k => {
              const value = Number(device[k])
              const isPercentage = k.includes('soc')
              const isCritical = isPercentage && value < 20
              
              return (
                <div 
                  key={k} 
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    backgroundColor: isCritical ? '#fee2e2' : '#f9fafb',
                    border: isCritical ? '1px solid #fecaca' : 'none'
                  }}
                >
                  <div style={{ fontSize: '11px', color: '#6b7280', marginBottom: '4px', textTransform: 'capitalize' }}>
                    {k.replace(/_/g, ' ')}
                  </div>
                  <div style={{
                    fontSize: '24px',
                    fontWeight: 'bold',
                    color: isCritical ? '#dc2626' : '#1f2937'
                  }}>
                    {value.toFixed(2)}{isPercentage && '%'}
                  </div>
                  {isPercentage && (
                    <div style={{ marginTop: '8px', width: '100%', backgroundColor: '#e5e7eb', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
                      <div style={{
                        height: '8px',
                        borderRadius: '4px',
                        backgroundColor: value < 20 ? '#ef4444' : value < 50 ? '#eab308' : '#10b981',
                        width: `${Math.min(value, 100)}%`,
                        transition: 'width 0.3s'
                      }} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {rl_action !== undefined && (
          <RLActionDisplay rl_action={rl_action} deviceId={device.device_id} />
        )}

        {advisory && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '8px 12px',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              backgroundColor: advisory.priority === 'high' ? '#fee2e2' : advisory.priority === 'medium' ? '#fef3c7' : '#dbeafe',
              color: advisory.priority === 'high' ? '#991b1b' : advisory.priority === 'medium' ? '#92400e' : '#1e40af',
              border: `2px solid ${advisory.priority === 'high' ? '#fca5a5' : advisory.priority === 'medium' ? '#fcd34d' : '#93c5fd'}`
            }}>
              {advisory.priority === 'high' ? '🚨' : advisory.priority === 'medium' ? '⚠️' : 'ℹ️'}
              {advisory.advisory}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function ConnectionStatus({ status }) {
  const statusConfig = {
    connecting: { color: '#eab308', icon: '⏳', text: 'Connecting...' },
    connected: { color: '#10b981', icon: '✓', text: 'Connected' },
    disconnected: { color: '#ef4444', icon: '✗', text: 'Disconnected' },
    error: { color: '#ef4444', icon: '⚠', text: 'Error' }
  }
  const config = statusConfig[status] || statusConfig.disconnected
  
  return (
    <div style={{
      backgroundColor: config.color,
      color: 'white',
      padding: '8px 16px',
      borderRadius: '20px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      fontWeight: '600',
      boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
    }}>
      <span style={{ animation: status === 'connecting' ? 'pulse 2s infinite' : 'none' }}>{config.icon}</span>
      <span>{config.text}</span>
    </div>
  )
}

function SystemOverview({ devices }) {
  const totalPower = devices.reduce((sum, d) => sum + (d.power_kW || 0), 0)
  const socDevices = devices.filter(d => d.soc !== undefined && d.soc !== null)
  const avgSoc = socDevices.length > 0 ? socDevices.reduce((sum, d) => sum + d.soc, 0) / socDevices.length : 0
  const totalDemand = devices.reduce((sum, d) => sum + (d.demand_kW || 0), 0)
  const activeDevices = devices.length

  const statCards = [
    { label: 'Total Power', value: `${totalPower.toFixed(2)} kW`, gradient: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' },
    { label: 'Avg Battery SoC', value: `${avgSoc.toFixed(1)}%`, gradient: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' },
    { label: 'Total Demand', value: `${totalDemand.toFixed(2)} kW`, gradient: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' },
    { label: 'Active Devices', value: activeDevices, gradient: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' }
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
      {statCards.map((card, idx) => (
        <div key={idx} style={{
          background: card.gradient,
          borderRadius: '16px',
          padding: '20px',
          color: 'white',
          boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'
        }}>
          <div style={{ fontSize: '14px', opacity: 0.9, marginBottom: '4px' }}>{card.label}</div>
          <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{card.value}</div>
        </div>
      ))}
    </div>
  )
}

export default function App() {
  const [live, setLive] = useState({})
  const [wsStatus, setWsStatus] = useState('connecting')
  const [lastAction, setLastAction] = useState(0)
  const [deviceHistory, setDeviceHistory] = useState({})

  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return
      setWsStatus('connecting')
      const ws = new WebSocket(WS_BASE)
      wsRef.current = ws

      ws.onopen = () => { 
        if (!mountedRef.current) return
        setWsStatus('connected')
      }
      
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          console.log("WS message:", msg)   // 👈 this will show the full payload
          // keep your existing logic here
          if (msg.device_id) {
            setLive(prev => ({
              ...prev,
              [msg.device_id]: { ...prev[msg.device_id], ...msg, ts: Date.now(), rl_action: msg.rl_action }
            }))

            if (msg.rl_action !== undefined) {
              setLastAction(msg.rl_action)
            }

            setDeviceHistory(prev => {
              const deviceHist = prev[msg.device_id] || []
              const timestamp = new Date()
              const newEntry = {
                time: timestamp.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                timestamp: timestamp.getTime(),
                value: msg.power_kW || msg.soc || msg.ev_soc || msg.demand_kW || msg.price || 0,
                rl_action: msg.rl_action !== undefined ? msg.rl_action : null
              }
              return {
                ...prev,
                [msg.device_id]: [...deviceHist, newEntry].slice(-MAX_HISTORY_POINTS)
              }
            })
          }
        } catch (err) {
          console.error("WebSocket message error:", err)
        }
      }

      ws.onerror = () => {
        if (mountedRef.current) setWsStatus('error')
      }
      
      ws.onclose = () => {
        if (!mountedRef.current) return
        setWsStatus('disconnected')
        reconnectTimerRef.current = setTimeout(() => {
          if (mountedRef.current) connect()
        }, RECONNECT_DELAY)
      }
    }

    connect()
    
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const devices = Object.values(live)

  const getAdvisory = (device) => {
    if (!device) return null
    
    if (device.device_id === "batt-01") {
      if (device.soc !== undefined && device.soc < 20) {
        return { advisory: "Low SoC! Charge immediately", priority: "high" }
      }
      if (device.rl_action === 1) {
        return { advisory: "RL Agent: Charging battery", priority: "medium" }
      }
      if (device.rl_action === 2) {
        return { advisory: "RL Agent: Discharging battery", priority: "medium" }
      }
    }
    
    if (device.device_id === "ev-01") {
      if (device.ev_soc !== undefined && device.ev_soc < 20) {
        return { advisory: "EV low, charge soon", priority: "high" }
      }
      if (device.rl_action === 3) {
        return { advisory: "RL Agent: Charging EV", priority: "medium" }
      }
    }
    
    if (device.device_id === "grid-01" && device.price !== undefined && device.price > 6) {
      return { advisory: "Expensive grid power", priority: "warning" }
    }
    
    if (device.device_id === "load-01" && device.demand_kW !== undefined && device.demand_kW > 2.5) {
      return { advisory: "High load demand", priority: "warning" }
    }
    
    if (device.device_id === "pv-01" && device.power_kW !== undefined && device.power_kW > 4) {
      return { advisory: "High solar generation", priority: "info" }
    }
    
    return null
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(to bottom right, #f9fafb, #f3f4f6)',
      padding: '24px'
    }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 style={{
              fontSize: '36px',
              fontWeight: 'bold',
              background: 'linear-gradient(to right, #2563eb, #7c3aed)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              marginBottom: '8px'
            }}>
              ⚡ VidyutAI — EMS Dashboard
            </h1>
            <p style={{ color: '#6b7280', fontSize: '18px' }}>Real-time Energy Management System</p>
          </div>
          <ConnectionStatus status={wsStatus} />
        </div>

        <SystemOverview devices={devices} />

        <div>
          {devices.map(d => {
            // Use the real RL action from backend
            const deviceRlAction = d.rl_action !== undefined ? d.rl_action : null
            
            return (
              <div key={d.device_id}>
                <DeviceCard 
                  device={d} 
                  rl_action={deviceRlAction} 
                  advisory={getAdvisory(d)} 
                />

                {deviceHistory[d.device_id]?.length > 1 && (
                  <div style={{
                    backgroundColor: 'white',
                    borderRadius: '16px',
                    boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
                    padding: '24px',
                    marginTop: '16px',
                    marginBottom: '24px'
                  }}>
                    <h6 style={{ fontSize: '18px', fontWeight: 'bold', color: '#1f2937', marginBottom: '16px' }}>
                      {deviceIcons[d.device_id] || '📊'} {d.device_id} — Telemetry Timeline
                    </h6>
                    <ResponsiveContainer width="100%" height={250}>
                      <AreaChart data={deviceHistory[d.device_id]}>
                        <defs>
                          <linearGradient id={`color-${d.device_id}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={deviceColors[d.device_id] || '#6b7280'} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={deviceColors[d.device_id] || '#6b7280'} stopOpacity={0.1}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                        <XAxis 
                          dataKey="time" 
                          tick={{ fontSize: 12 }}
                          stroke="#6b7280"
                        />
                        <YAxis 
                          tick={{ fontSize: 12 }}
                          stroke="#6b7280"
                        />
                        <Tooltip 
                          contentStyle={{
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            border: '1px solid #e5e7eb',
                            borderRadius: '8px',
                            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                          }}
                          formatter={(value, name) => {
                            if (name === 'RL Action') {
                              return [rlActionMap[value]?.text || value, name]
                            }
                            return [typeof value === 'number' ? value.toFixed(2) : value, name]
                          }}
                        />
                        <Legend />
                        <Area 
                          type="monotone" 
                          dataKey="value" 
                          stroke={deviceColors[d.device_id] || '#6b7280'}
                          fillOpacity={1}
                          fill={`url(#color-${d.device_id})`}
                          strokeWidth={2}
                          name="Telemetry"
                        />
                        <Line 
                          type="stepAfter" 
                          dataKey="rl_action" 
                          stroke="#f59e0b" 
                          strokeWidth={3}
                          dot={{ fill: '#f59e0b', r: 4 }}
                          name="RL Action"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {devices.length === 0 && wsStatus === 'connected' && (
          <div style={{
            backgroundColor: 'white',
            borderRadius: '16px',
            boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
            padding: '48px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '60px', marginBottom: '16px' }}>📡</div>
            <h3 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937', marginBottom: '8px' }}>
              Waiting for Device Data
            </h3>
            <p style={{ color: '#6b7280' }}>
              No devices detected yet. Data will appear when devices start transmitting.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}