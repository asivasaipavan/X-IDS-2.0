import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertOctagon, AlertTriangle, ArrowDownRight, ArrowUpRight, Bell, Boxes, BrainCircuit,
  Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, CloudDownload, Cpu, Database, Download,
  FileSearch, FileText, Fingerprint, Gauge, Globe2, HardDrive, Layers3, LayoutDashboard, Lock,
  LockKeyhole, Mail, Menu, Network, PanelLeftClose, Play, Radio, RefreshCw, Search, Server,
  Settings, Shield, ShieldAlert, ShieldCheck, Square, Terminal, Upload, Users, Wifi, X, Zap,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
// import ReactFlow, { Background, Controls, MiniMap } from '@xyflow/react'
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api, connectLive } from './api'

const nav = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, group: 'OPERATIONS' },
  { id: 'monitor', label: 'Live monitoring', icon: Radio, group: 'OPERATIONS' },
  { id: 'alerts', label: 'Threat alerts', icon: ShieldAlert, group: 'OPERATIONS', badge: true },
  { id: 'explain', label: 'Explainable AI', icon: BrainCircuit, group: 'INTELLIGENCE' },
  { id: 'pcap', label: 'PCAP analyzer', icon: FileSearch, group: 'INTELLIGENCE' },
  { id: 'intel', label: 'Threat intelligence', icon: Globe2, group: 'INTELLIGENCE' },
  { id: 'topology', label: 'Network topology', icon: Network, group: 'INTELLIGENCE' },
  { id: 'reports', label: 'Reports & response', icon: FileText, group: 'MANAGEMENT' },
  { id: 'settings', label: 'Configuration', icon: Settings, group: 'MANAGEMENT' },
  { id: 'users', label: 'Users & roles', icon: Users, group: 'MANAGEMENT', adminOnly: true },
]
const tooltipStyle = { background: '#18181D', border: '1px solid #303038', borderRadius: 12, color: '#dbeafe', fontSize: 12 }
const chartColors = ['#FB3C5B', '#818cf8', '#f59e0b', '#f87171', '#34d399', '#a78bfa']

function messageOf(err) { return err?.response?.data?.error || err?.message || 'Something went wrong.' }
function fmtNum(n) { return Number(n || 0).toLocaleString('en-IN') }
function fmtBytes(n) { const v = Number(n || 0); return v > 1e9 ? `${(v / 1e9).toFixed(2)} GB` : v > 1e6 ? `${(v / 1e6).toFixed(1)} MB` : v > 1e3 ? `${(v / 1e3).toFixed(1)} KB` : `${fmtNum(v)} B` }
function timeAgo(v) { if (!v) return '—'; const s = Math.max(0, Math.floor((Date.now() - new Date(v).getTime()) / 1000)); return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.floor(s / 60)}m ago` : `${Math.floor(s / 3600)}h ago` }
function dateTime(v) { return v ? new Date(v).toLocaleString() : '—' }
function cx(...v) { return v.filter(Boolean).join(' ') }

function Badge({ children, tone = 'slate' }) {
  const styles = { slate: 'bg-slate-700/35 text-slate-300 border-slate-600/30', green: 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20', red: 'bg-rose-400/10 text-rose-300 border-rose-400/20', amber: 'bg-amber-400/10 text-amber-300 border-amber-400/20', cyan: 'bg-rose-400/10 text-rose-300 border-rose-400/20', violet: 'bg-violet-400/10 text-violet-300 border-violet-400/20' }
  return <span className={cx('inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[.12em]', styles[tone] || styles.slate)}>{children}</span>
}
function Severity({ level }) { const tone = level === 'critical' || level === 'high' ? 'red' : level === 'medium' ? 'amber' : level === 'low' ? 'green' : 'slate'; return <Badge tone={tone}><span className="h-1.5 w-1.5 rounded-full bg-current" />{level || 'info'}</Badge> }
function Button({ children, onClick, variant = 'primary', disabled, className = '', type = 'button' }) {
  const styles = variant === 'primary' ? 'bg-rose-400 text-slate-950 hover:bg-rose-300 shadow-[0_7px_26px_rgba(34,211,238,.13)]' : variant === 'danger' ? 'bg-rose-500/10 text-rose-300 border border-rose-400/20 hover:bg-rose-500/20' : variant === 'soft' ? 'bg-slate-800/80 text-slate-200 border border-slate-700 hover:border-slate-500' : 'text-slate-400 hover:text-white hover:bg-slate-800'
  return <button type={type} disabled={disabled} onClick={onClick} className={cx('inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2.5 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-40', styles, className)}>{children}</button>
}
function Panel({ children, className = '' }) { return <section className={cx('panel rounded-2xl', className)}>{children}</section> }
function SectionTitle({ eyebrow, title, description, right }) { return <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><div className="mb-1 text-[10px] font-bold uppercase tracking-[.22em] text-rose-400">{eyebrow}</div><h2 className="text-xl font-bold tracking-tight text-white">{title}</h2>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div>{right}</div> }
function StatCard({ label, value, foot, icon: Icon, color = 'cyan', trend }) {
  const colors = { cyan: 'text-rose-300 bg-rose-400/10', violet: 'text-violet-300 bg-violet-400/10', amber: 'text-amber-300 bg-amber-400/10', rose: 'text-rose-300 bg-rose-400/10', green: 'text-emerald-300 bg-emerald-400/10' }
  return <Panel className="relative overflow-hidden p-4 sm:p-5"><div className="absolute -right-7 -top-8 h-28 w-28 rounded-full bg-white/[.02] blur-2xl"/><div className="flex items-start justify-between"><div className="text-[11px] font-semibold uppercase tracking-[.13em] text-slate-500">{label}</div><div className={cx('rounded-xl p-2.5', colors[color])}><Icon size={17}/></div></div><div className="mt-4 flex items-end justify-between gap-2"><div className="text-2xl font-bold tracking-tight text-white sm:text-[27px]">{value}</div>{trend && <div className="mb-1 text-[10px] font-semibold text-emerald-300">{trend}</div>}</div><div className="mt-1 text-[11px] text-slate-500">{foot}</div></Panel>
}
function EmptyState({ icon: Icon = CircleHelp, title, text }) { return <div className="flex flex-col items-center justify-center py-12 text-center"><div className="mb-3 rounded-2xl border border-slate-700 bg-slate-800/60 p-4 text-slate-400"><Icon size={24}/></div><div className="text-sm font-semibold text-slate-200">{title}</div><p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">{text}</p></div> }

function EventsTable({ rows = [], onExplain, onAcknowledge, onBlock, compact = false }) {
  if (!rows.length) return <EmptyState icon={ShieldCheck} title="No network flows recorded yet" text="Start live monitoring or upload a PCAP capture to populate this view." />
  return <div className="scrollbar overflow-x-auto"><table className="w-full min-w-[760px] text-left"><thead><tr className="border-b border-slate-800 text-[10px] uppercase tracking-[.13em] text-slate-500"><th className="px-4 py-3 font-semibold">Flow / time</th><th className="px-4 py-3 font-semibold">Source</th><th className="px-4 py-3 font-semibold">Destination</th><th className="px-4 py-3 font-semibold">Protocol</th><th className="px-4 py-3 font-semibold">Classification</th><th className="px-4 py-3 font-semibold">Confidence</th>{!compact && <th className="px-4 py-3 font-semibold">Actions</th>}</tr></thead><tbody>{rows.map(row => <tr key={row.id} className="border-b border-slate-800/70 text-xs transition hover:bg-slate-800/25"><td className="px-4 py-3"><div className="font-semibold text-slate-200">FLOW-{String(row.id).padStart(5, '0')}</div><div className="mt-1 text-[10px] text-slate-500">{timeAgo(row.timestamp)} · {row.packets} pkts</div></td><td className="mono px-4 py-3 text-slate-300">{row.src_ip}<span className="text-slate-600">:{row.src_port}</span></td><td className="mono px-4 py-3 text-slate-300">{row.dst_ip}<span className="text-slate-600">:{row.dst_port}</span></td><td className="px-4 py-3"><Badge tone="slate">{row.protocol}</Badge></td><td className="px-4 py-3"><div className="font-semibold text-slate-200">{row.anomaly_flag && ['Normal','Benign'].includes(row.prediction) ? 'Normal · anomaly' : row.prediction}</div><div className="mt-1"><Severity level={row.severity}/></div></td><td className="px-4 py-3"><div className="flex items-center gap-2"><div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-rose-400" style={{ width: `${Math.max(0, Math.min(100, row.confidence * 100))}%` }}/></div><span className="mono text-slate-400">{(row.confidence * 100).toFixed(1)}%</span></div></td>{!compact && <td className="px-4 py-3"><div className="flex items-center gap-1.5"><button onClick={() => onExplain?.(row)} className="rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] text-rose-300 hover:bg-rose-400/10">Explain</button>{!row.acknowledged && <button onClick={() => onAcknowledge?.(row.id)} className="rounded-lg border border-slate-700 px-2 py-1.5 text-[10px] text-slate-400 hover:text-white">Ack</button>}{onBlock && row.prediction !== 'Normal' && row.prediction !== 'UNSCORABLE' && !row.blocked && <button onClick={() => onBlock?.(row.src_ip)} className="rounded-lg border border-rose-400/20 px-2 py-1.5 text-[10px] text-rose-300 hover:bg-rose-500/10">Block</button>}</div></td>}</tr>)}</tbody></table></div>
}

function App() {
  const [page, setPage] = useState('overview')
  const [summary, setSummary] = useState(null)
  const [events, setEvents] = useState([])
  const [interfaces, setInterfaces] = useState([])
  const [selectedInterface, setSelectedInterface] = useState('')
  const [monitor, setMonitor] = useState({ running: false, packets_seen: 0, bytes_seen: 0, protocols: {} })
  const [socketUp, setSocketUp] = useState(false)
  const [toast, setToast] = useState(null)
  const [search, setSearch] = useState('')
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [config, setConfig] = useState({ auto_block_enabled: false, email_alerts_enabled: false, detection_threshold: 0.85 })
  const [busy, setBusy] = useState(false)
  const [clock, setClock] = useState(new Date())
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)

  const notify = (text, type = 'ok') => { setToast({ text, type }); window.setTimeout(() => setToast(null), 4500) }
  const refresh = useCallback(async () => {
    try {
      const [s, e, m] = await Promise.all([api.summary(), api.events(), api.monitorStatus()])
      setSummary(s); setEvents(e); setMonitor(m)
    } catch (err) { notify(`API unavailable: ${messageOf(err)}`, 'error') }
  }, [])

  useEffect(() => {
    api.csrf().catch(() => {})
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setAuthLoading(false))
  }, [])

  useEffect(() => {
    if (!user) return undefined
    refresh()
    api.interfaces().then(r => { setInterfaces(r.interfaces || []); setSelectedInterface(r.interfaces?.[0]?.name || '') }).catch(() => {})
    api.config().then(setConfig).catch(() => {})
    const timer = window.setInterval(() => { refresh(); setClock(new Date()) }, 5000)
    const socket = connectLive(event => { setEvents(old => [event, ...old.filter(x => x.id !== event.id)].slice(0, 200)); setSummary(old => old ? { ...old, recent_events: [event, ...(old.recent_events || []).filter(x => x.id !== event.id)].slice(0, 8) } : old) }, setSocketUp)
    return () => { window.clearInterval(timer); socket.close() }
  }, [refresh, user])

  const loadEvents = async (params = {}) => { try { setEvents(await api.events(params)) } catch (err) { notify(messageOf(err), 'error') } }
  const start = async () => { try { setBusy(true); const r = await api.startMonitor(selectedInterface); setMonitor(r); notify(`Capture started on ${r.interface || 'default interface'}.`); setPage('monitor') } catch (err) { notify(messageOf(err), 'error') } finally { setBusy(false) } }
  const stop = async () => { try { setBusy(true); setMonitor(await api.stopMonitor()); notify('Network capture stopped.') } catch (err) { notify(messageOf(err), 'error') } finally { setBusy(false); refresh() } }
  const explain = row => { setSelectedEvent(row); setPage('explain') }
  const ack = async id => { try { await api.acknowledge(id); notify('Alert acknowledged.'); refresh() } catch (err) { notify(messageOf(err), 'error') } }
  const block = async ip => { if (!window.confirm(`Add Windows/Linux firewall block rules for public IP ${ip}? This action may interrupt connectivity.`)) return; try { const r = await api.block(ip); notify(r.message || 'Firewall rule added.') ; refresh() } catch (err) { notify(messageOf(err), 'error') } }
  const setConfigValue = async data => { try { const r = await api.updateConfig(data); setConfig(r); notify('Configuration saved.') } catch (err) { notify(messageOf(err), 'error') } }
  const visibleEvents = useMemo(() => events.filter(e => !search || `${e.src_ip} ${e.dst_ip} ${e.prediction} ${e.protocol}`.toLowerCase().includes(search.toLowerCase())), [events, search])
  const alertCount = summary?.unacknowledged || 0
  const handleLogin = async (username, password) => { try { const loggedIn = await api.login(username, password); setUser(loggedIn); notify(`Welcome, ${loggedIn.username}.`) } catch (err) { throw new Error(messageOf(err)) } }
  const handleRegister = async (data) => {
    try {
      await api.csrf()
      await api.register(data)
      const loggedIn = await api.login(data.username, data.password)
      setUser(loggedIn)
      notify(`Welcome to X-IDS, ${loggedIn.username}.`)
    } catch (err) {
      throw new Error(messageOf(err))
    }
  }
  const handleLogout = async () => { try { await api.logout() } catch { /* session may already be expired */ } setUser(null); setSummary(null); setEvents([]); setPage('overview') }
  if (authLoading) return <div className="flex min-h-screen items-center justify-center bg-[#09090B] text-sm text-slate-400"><RefreshCw className="mr-3 animate-spin" size={16}/>Checking local session…</div>
  // if (!user) return <LoginPage onLogin={handleLogin}/>
  if (!user) return <LoginPage onLogin={handleLogin} onRegister={handleRegister}/>
  return <div className="min-h-screen bg-[#09090B] text-slate-200">
    <div className="fixed inset-0 pointer-events-none grid-bg opacity-40"/>
    <div className="relative mx-auto flex min-h-screen max-w-[1800px]">
      <aside className="hidden w-[250px] shrink-0 flex-col border-r border-slate-800/80 bg-[#111114]/90 px-4 py-5 lg:flex">
        <div className="mb-9 flex items-center gap-3 px-2"><div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-rose-400 text-slate-950 shadow-[0_0_30px_rgba(34,211,238,.22)]"><Shield size={22}/><span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-[#111114] bg-emerald-400"/></div><div><div className="text-[15px] font-extrabold tracking-[.13em] text-white">X<span className="text-rose-300">-</span>IDS</div><div className="text-[9px] font-bold uppercase tracking-[.23em] text-slate-500">Security operations</div></div></div>
        {['OPERATIONS','INTELLIGENCE','MANAGEMENT'].map(group => <div key={group} className="mb-6"><div className="mb-2 px-3 text-[9px] font-extrabold tracking-[.22em] text-slate-600">{group}</div><div className="space-y-1">{nav.filter(n => n.group === group && (!n.adminOnly || user.is_admin)).map(item => { const Icon = item.icon; const active = page === item.id; return <button key={item.id} onClick={() => setPage(item.id)} className={cx('flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs font-semibold transition', active ? 'bg-rose-400/10 text-rose-200 ring-1 ring-rose-300/15' : 'text-slate-500 hover:bg-slate-800/60 hover:text-slate-200')}><Icon size={16}/><span className="flex-1">{item.label}</span>{item.badge && alertCount > 0 && <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-[9px] font-bold text-white">{alertCount > 99 ? '99+' : alertCount}</span>}</button> })}</div></div>)}
        <div className="mt-auto rounded-2xl border border-rose-400/15 bg-gradient-to-br from-rose-500/10 to-indigo-500/5 p-3"><div className="mb-2 flex items-center gap-2 text-xs font-bold text-rose-200"><Activity size={14}/> Model engine</div><div className="flex items-center justify-between text-[10px] text-slate-500"><span>LSTM</span><Badge tone={summary?.models?.lstm_ready ? 'green' : 'amber'}>{summary?.models?.lstm_ready ? 'READY' : 'OFFLINE'}</Badge></div><div className="mt-2 flex items-center justify-between text-[10px] text-slate-500"><span>TCN</span><Badge tone={summary?.models?.tcn_ready ? 'green' : 'amber'}>{summary?.models?.tcn_ready ? 'READY' : 'OFFLINE'}</Badge></div><div className="mt-3 h-1 rounded-full bg-slate-800"><div className="h-full w-3/4 rounded-full bg-gradient-to-r from-rose-400 to-indigo-400"/></div><div className="mt-2 text-[9px] text-slate-600">CIC-IDS2017 · 76 input features</div></div>
        <div className="mt-4 px-2 text-[9px] text-slate-600">X-IDS 2.0 · LOCAL DEPLOYMENT</div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-slate-800/80 bg-[#111114]/90 px-4 backdrop-blur-xl sm:px-7">
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 lg:hidden"><Shield size={18} className="text-rose-300"/></div><div><div className="text-sm font-bold text-white">{nav.find(n => n.id === page)?.label || 'Overview'}</div><div className="mt-0.5 text-[10px] text-slate-500">Security telemetry / <span className="text-rose-300">{page.toUpperCase()}</span></div></div></div>
          <div className="flex items-center gap-3"><div className="hidden text-right sm:block"><div className="mono text-xs text-slate-300">{clock.toLocaleTimeString()}</div><div className="text-[9px] text-slate-600">{clock.toLocaleDateString()}</div></div><div className="hidden h-8 w-px bg-slate-800 sm:block"/><div className="flex items-center gap-2 rounded-full border border-slate-700/80 bg-slate-900/70 px-3 py-2"><span className={cx('h-1.5 w-1.5 rounded-full', monitor.running ? 'pulse-dot bg-emerald-400' : 'bg-slate-600')}/><span className="text-[10px] font-bold text-slate-400">{monitor.running ? 'CAPTURING' : 'STANDBY'}</span></div><div className="hidden items-center gap-1.5 rounded-full border border-slate-700/80 px-2.5 py-2 text-[10px] text-slate-500 md:flex"><span className={cx('h-1.5 w-1.5 rounded-full', socketUp ? 'bg-emerald-400' : 'bg-amber-400')}/>{socketUp ? 'WS CONNECTED' : 'WS RECONNECTING'}</div><div className="hidden text-[10px] text-slate-400 sm:block">{user.username}{user.is_admin ? ' · ADMIN' : ''}</div><button onClick={handleLogout} title="Sign out" className="rounded-xl border border-slate-700 bg-slate-900 p-2 text-slate-400 transition hover:text-rose-300"><LockKeyhole size={15}/></button><button onClick={() => refresh()} className="rounded-xl border border-slate-700 bg-slate-900 p-2 text-slate-400 transition hover:text-rose-300"><RefreshCw size={15}/></button></div>
        </header>

        <div className="relative z-10 p-4 sm:p-7">
          {page === 'overview' && <Overview summary={summary} events={summary?.recent_events || events.slice(0, 8)} onExplain={explain} onAcknowledge={ack} onBlock={block} onMonitor={() => setPage('monitor')} />}
          {page === 'monitor' && <MonitorPage monitor={monitor} interfaces={interfaces} selectedInterface={selectedInterface} setSelectedInterface={setSelectedInterface} start={start} stop={stop} busy={busy} refresh={refresh} />}
          {page === 'alerts' && <AlertsPage events={visibleEvents.filter(e => e.anomaly_flag || !['Normal','UNSCORABLE','Pending'].includes(e.prediction))} search={search} setSearch={setSearch} onExplain={explain} onAcknowledge={ack} onBlock={user.is_admin ? block : undefined} />}
          {page === 'explain' && <ExplainPage event={selectedEvent || events.find(e => e.prediction !== 'Normal')} onSelect={setSelectedEvent} events={events} notify={notify} />}
          {page === 'pcap' && <PcapPage notify={notify} />}
          {page === 'intel' && <IntelPage notify={notify} />}
          {page === 'topology' && <TopologyPage />}
          {page === 'reports' && <ReportsPage notify={notify} block={block} isAdmin={user.is_admin} />}
          {page === 'settings' && <SettingsPage config={config} setConfigValue={setConfigValue} notify={notify} isAdmin={user.is_admin} />}
          {page === 'users' && user.is_admin && <UsersPage notify={notify} />}
          <footer className="mt-10 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-4 text-[10px] text-slate-600"><span>X-IDS 2.0 · Explainable intrusion detection</span><span>Local-first processing · Model predictions require analyst validation</span></footer>
        </div>
      </main>
    </div>
    {toast && <div className={cx('fixed bottom-5 right-5 z-50 flex max-w-sm items-center gap-3 rounded-xl border px-4 py-3 text-xs shadow-2xl', toast.type === 'error' ? 'border-rose-400/30 bg-[#21121d] text-rose-200' : 'border-emerald-400/20 bg-[#0d211f] text-emerald-200')}><span className="rounded-lg bg-white/5 p-1.5">{toast.type === 'error' ? <AlertTriangle size={15}/> : <CheckCircle2 size={15}/>}</span>{toast.text}<button onClick={() => setToast(null)} className="ml-2 text-slate-500"><X size={14}/></button></div>}
  </div>
}


function LoginPage({ onLogin, onRegister }) {
  const [mode, setMode] = useState('login')
  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setError('')
    setBusy(true)

    try {
      if (mode === 'register') {
        if (password !== confirmPassword) {
          throw new Error('Passwords do not match.')
        }

        await onRegister({
          full_name: fullName,
          username,
          email,
          password,
          confirm_password: confirmPassword
        })
      } else {
        await onLogin(username, password)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const fieldClass = "w-full rounded-xl border border-slate-700 bg-[#111114] px-3 py-3 text-sm outline-none focus:border-rose-400"

  return (
    <div className="grid min-h-screen place-items-center bg-[#09090B] px-4">
      <div className="pointer-events-none fixed inset-0 grid-bg opacity-40"/>
      <div className="panel relative w-full max-w-[420px] rounded-3xl p-7">

        <div className="mb-7 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-400 text-slate-950">
            <Shield size={25}/>
          </div>
          <div>
            <div className="text-lg font-extrabold tracking-[.13em] text-white">X-IDS 2.0</div>
            <div className="text-[9px] font-bold uppercase tracking-[.2em] text-slate-500">
              Local security operations
            </div>
          </div>
        </div>

        <div className="text-xl font-bold text-white">
          {mode === 'login' ? 'Sign in to your sensor' : 'Create your account'}
        </div>

        <p className="mt-1 text-xs text-slate-500">
          {mode === 'login'
            ? 'Sign in using your X-IDS account.'
            : 'Register as an X-IDS security analyst.'}
        </p>

        <div className="mt-5 grid grid-cols-2 gap-2">
          <button type="button" onClick={() => {setMode('login');setError('')}}
            className={`rounded-xl py-2 text-xs font-bold ${mode === 'login' ? 'bg-rose-400 text-slate-950' : 'bg-slate-800 text-slate-400'}`}>
            Sign In
          </button>
          <button type="button" onClick={() => {setMode('register');setError('')}}
            className={`rounded-xl py-2 text-xs font-bold ${mode === 'register' ? 'bg-rose-400 text-slate-950' : 'bg-slate-800 text-slate-400'}`}>
            Create Account
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-3">

          {mode === 'register' && <>
            <input required value={fullName}
              onChange={e=>setFullName(e.target.value)}
              className={fieldClass} placeholder="Full name"/>

            <input required type="email" value={email}
              onChange={e=>setEmail(e.target.value)}
              className={fieldClass} placeholder="Email address"/>
          </>}

          <input required minLength={3} value={username}
            onChange={e=>setUsername(e.target.value)}
            className={fieldClass} placeholder="Username"/>

          <input required type="password"
            minLength={8}
            value={password}
            onChange={e=>setPassword(e.target.value)}
            className={fieldClass} placeholder="Password"/>

          {mode === 'register' && <>
            <input required type="password" value={confirmPassword}
              onChange={e=>setConfirmPassword(e.target.value)}
              className={fieldClass} placeholder="Confirm password"/>
          </>}

          {error && <div className="rounded-xl border border-rose-400/20 bg-rose-400/5 p-3 text-xs text-rose-300">{error}</div>}

          <Button type="submit" className="w-full" disabled={busy}>
            {busy
              ? 'Please wait...'
              : mode === 'login' ? 'Sign in securely' : 'Create Analyst Account'}
            <ChevronRight size={14}/>
          </Button>
        </form>

        <div className="mt-5 border-t border-slate-800 pt-4 text-[10px] leading-5 text-slate-600">
          X-IDS is a local-first security application. Public registration creates Analyst accounts only.
        </div>
      </div>
    </div>
  )
}


function UsersPage({ notify }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({username:'',email:'',password:'',role:'analyst'})
  const [busy, setBusy] = useState(false)
  const load = () => api.users().then(setUsers).catch(e=>notify(messageOf(e),'error'))
  useEffect(()=>{load()},[])
  const create = async e => { e.preventDefault(); try { setBusy(true); await api.createUser(form); setForm({username:'',email:'',password:'',role:'analyst'}); notify('User account created.'); load() } catch(err) { notify(messageOf(err),'error') } finally { setBusy(false) } }
  return <><SectionTitle eyebrow="Access control" title="Users and roles" description="Create separate analyst and administrator accounts. Only administrators can manage users."/><div className="grid gap-4 xl:grid-cols-[.9fr_1.1fr]"><Panel className="p-5"><div className="mb-4 text-sm font-bold text-white">Create user</div><form onSubmit={create} className="space-y-3"><input required minLength={3} value={form.username} onChange={e=>setForm({...form,username:e.target.value})} placeholder="Username" className="w-full rounded-xl border border-slate-700 bg-[#111114] px-3 py-2.5 text-xs outline-none focus:border-rose-400"/><input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="Email (optional)" className="w-full rounded-xl border border-slate-700 bg-[#111114] px-3 py-2.5 text-xs outline-none focus:border-rose-400"/><input required minLength={10} type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder="Temporary password (10+ characters)" className="w-full rounded-xl border border-slate-700 bg-[#111114] px-3 py-2.5 text-xs outline-none focus:border-rose-400"/><select value={form.role} onChange={e=>setForm({...form,role:e.target.value})} className="w-full rounded-xl border border-slate-700 bg-[#111114] px-3 py-2.5 text-xs"><option value="analyst">Analyst</option><option value="admin">Administrator</option></select><Button type="submit" className="w-full" disabled={busy}><Users size={14}/>{busy?'Creating…':'Create account'}</Button></form></Panel><Panel className="overflow-hidden"><div className="border-b border-slate-800 px-5 py-4"><div className="text-sm font-bold text-white">Local accounts</div><div className="mt-1 text-[10px] text-slate-500">{users.length} user accounts</div></div><div className="divide-y divide-slate-800">{users.map(u=><div key={u.id} className="flex items-center justify-between gap-3 px-5 py-3"><div><div className="text-xs font-semibold text-slate-200">{u.username}</div><div className="mt-1 text-[10px] text-slate-500">{u.email || 'No email'} · {u.active?'Active':'Disabled'}</div></div><Badge tone={u.is_admin?'violet':'cyan'}>{u.is_admin?'ADMIN':'ANALYST'}</Badge></div>)}</div></Panel></div></>
}

function Overview({ summary, events, onExplain, onAcknowledge, onBlock, onMonitor }) {
  const protocol = Object.entries(summary?.protocol_distribution || {}).map(([name, value]) => ({ name, value }))
  const ready = summary?.models?.ready
  return <>
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4"><div><div className="mb-2 flex items-center gap-2"><Badge tone="cyan">LOCAL SENSOR</Badge><Badge tone={ready ? 'green' : 'amber'}>{ready ? 'ML MODELS READY' : 'MODEL CHECK REQUIRED'}</Badge>{summary?.risk_trend && <Badge tone={summary.risk_trend.direction==='rising'?'red':summary.risk_trend.direction==='falling'?'green':'slate'}>RISK TREND {summary.risk_trend.direction.toUpperCase()}</Badge>}</div><h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-[30px]">Security overview<span className="text-rose-300">.</span></h1><p className="mt-1 text-sm text-slate-500">A live view of network activity, model detections and threat posture.</p></div><Button onClick={onMonitor}><Radio size={14}/> Open live monitor <ChevronRight size={14}/></Button></div>
    {!ready && <div className="mb-5 rounded-xl border border-amber-400/20 bg-amber-400/[.06] p-3 text-xs leading-5 text-amber-200"><strong>Model engine not ready.</strong> Check backend dependencies and the model artifact paths. Live packet capture may work, but events will be marked UNSCORABLE until a classifier loads.</div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="Flows observed · 24h" value={fmtNum(summary?.flows_24h)} foot="Captured or imported network flows" icon={Activity} color="cyan"/><StatCard label="Potential threats · 24h" value={fmtNum(summary?.attacks_24h)} foot="Attack predictions + anomalies" icon={ShieldAlert} color="rose"/><StatCard label="Anomalous flows · 24h" value={fmtNum(summary?.anomalies_24h)} foot="Isolation Forest outlier signals" icon={Fingerprint} color="violet"/><StatCard label="Packets processed · 24h" value={fmtNum(summary?.packets_24h)} foot={`${fmtBytes(summary?.bytes_24h)} total traffic`} icon={Layers3} color="violet"/><StatCard label="Critical detections" value={fmtNum(summary?.critical_24h)} foot={`${fmtNum(summary?.unacknowledged)} unacknowledged alerts`} icon={AlertOctagon} color="amber"/></div>
    <div className="mt-4 grid gap-4 xl:grid-cols-[1.65fr_1fr]"><Panel className="p-4 sm:p-5"><div className="mb-4 flex items-center justify-between"><div><div className="text-sm font-bold text-white">Traffic & detection activity</div><div className="mt-1 text-[10px] text-slate-500">Recorded flows across the last 12 hours</div></div><Badge tone="cyan">LAST 12 HOURS</Badge></div><div className="h-[230px] w-full">{(summary?.traffic_series || []).length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={summary.traffic_series}><defs><linearGradient id="flowFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#FB3C5B" stopOpacity={.25}/><stop offset="100%" stopColor="#FB3C5B" stopOpacity={0}/></linearGradient><linearGradient id="attackFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#fb7185" stopOpacity={.22}/><stop offset="100%" stopColor="#fb7185" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#303038" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="time" tick={{ fill:'#64748b', fontSize:10 }} axisLine={false} tickLine={false}/><YAxis tick={{ fill:'#64748b', fontSize:10 }} axisLine={false} tickLine={false} width={32}/><Tooltip contentStyle={tooltipStyle}/><Area type="monotone" dataKey="flows" stroke="#FB3C5B" strokeWidth={2} fill="url(#flowFill)"/><Area type="monotone" dataKey="attacks" stroke="#fb7185" strokeWidth={2} fill="url(#attackFill)"/></AreaChart></ResponsiveContainer> : <EmptyState title="Waiting for flow telemetry" text="Start the capture sensor or import a PCAP file to populate activity charts."/>}</div><div className="mt-3 flex gap-4 text-[10px] text-slate-500"><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-rose-400"/>Flows</span><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-rose-400"/>Attack predictions</span></div></Panel>
      <Panel className="p-4 sm:p-5"><div className="mb-2 text-sm font-bold text-white">Protocol distribution</div><div className="text-[10px] text-slate-500">Observed in recent 24-hour telemetry</div>{protocol.length ? <><div className="h-[190px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={protocol} dataKey="value" nameKey="name" innerRadius={55} outerRadius={78} paddingAngle={4}>{protocol.map((p, i) => <Cell key={p.name} fill={chartColors[i % chartColors.length]}/>)}</Pie><Tooltip contentStyle={tooltipStyle}/></PieChart></ResponsiveContainer></div><div className="space-y-2">{protocol.slice(0,5).map((p,i) => <div key={p.name} className="flex items-center justify-between text-xs"><span className="flex items-center gap-2 text-slate-400"><i className="h-2 w-2 rounded-full" style={{background:chartColors[i%chartColors.length]}}/>{p.name}</span><span className="mono text-slate-200">{fmtNum(p.value)}</span></div>)}</div></> : <EmptyState title="No protocols yet" text="Protocol statistics appear after packet capture or PCAP import."/>}</Panel></div>
    <Panel className="mt-4 overflow-hidden"><div className="flex items-center justify-between border-b border-slate-800 px-4 py-4 sm:px-5"><div><div className="text-sm font-bold text-white">Recent network events</div><div className="mt-1 text-[10px] text-slate-500">Latest classified flows from live and offline sources</div></div><Badge tone="slate">{events?.length || 0} RECORDS</Badge></div><EventsTable rows={events || []} compact onExplain={onExplain} onAcknowledge={onAcknowledge} onBlock={onBlock}/></Panel>
  </>
}

function MonitorPage({ monitor, interfaces, selectedInterface, setSelectedInterface, start, stop, busy, refresh }) {
  const [showGuide, setShowGuide] = useState(false)
  return <><SectionTitle eyebrow="Sensor control" title="Live network monitoring" description="Capture visible packets, assemble bidirectional flows and score them with the existing LSTM + TCN models." right={<Badge tone={monitor.running ? 'green' : 'slate'}>{monitor.running ? 'CAPTURE ACTIVE' : 'SENSOR STANDBY'}</Badge>}/>
    <Panel className="relative overflow-hidden p-5 sm:p-7"><div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-rose-400/[.07] blur-3xl"/><div className="relative flex flex-wrap items-center justify-between gap-5"><div className="flex items-center gap-4"><div className={cx('flex h-16 w-16 items-center justify-center rounded-2xl border', monitor.running ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-slate-700 bg-slate-800/60 text-slate-500')}><Radio size={27}/></div><div><div className="text-lg font-bold text-white">{monitor.running ? 'Sensor is capturing traffic' : 'Sensor is ready to start'}</div><div className="mt-1 text-xs text-slate-500">{monitor.interface || 'No network interface selected'} · {monitor.started_at ? `Started ${new Date(monitor.started_at).toLocaleTimeString()}` : 'Awaiting start command'}</div></div></div><div className="flex gap-2">{!monitor.running ? <Button onClick={start} disabled={busy}><Play size={14} fill="currentColor"/> Start capture</Button> : <Button variant="danger" onClick={stop} disabled={busy}><Square size={13} fill="currentColor"/> Stop capture</Button>}<Button variant="soft" onClick={refresh}><RefreshCw size={14}/></Button></div></div>
      <div className="mt-7 grid gap-3 sm:grid-cols-[1fr_auto]"><div><label className="mb-2 block text-[10px] font-bold uppercase tracking-[.15em] text-slate-500">Capture interface</label><select disabled={monitor.running} value={selectedInterface} onChange={e=>setSelectedInterface(e.target.value)} className="w-full rounded-xl border border-slate-700 bg-[#18181D] px-3 py-3 text-xs text-slate-200 outline-none focus:border-rose-400">{interfaces.map(i=><option key={i.name} value={i.name}>{i.name}{i.ipv4 && i.ipv4 !== '0.0.0.0' ? ` · ${i.ipv4}` : ''}</option>)}</select><p className="mt-2 text-[10px] text-slate-600">Choose your active Wi-Fi or Ethernet adapter. Refresh interfaces if your adapter is missing.</p></div><div className="flex items-end"><Button variant="soft" onClick={refresh}><RefreshCw size={13}/> Refresh interfaces</Button></div></div>
      {monitor.error && <div className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/5 p-3 text-xs text-rose-300">Capture error: {monitor.error}. On Windows, install Npcap and run the backend terminal as Administrator.</div>}
    </Panel>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="Packets captured" value={fmtNum(monitor.packets_seen)} foot="Since capture was started" icon={Layers3} color="cyan"/><StatCard label="Data captured" value={fmtBytes(monitor.bytes_seen)} foot="Observed packet bytes" icon={HardDrive} color="violet"/><StatCard label="TCP packets" value={fmtNum(monitor.protocols?.TCP)} foot="Transmission Control Protocol" icon={Network} color="green"/><StatCard label="UDP packets" value={fmtNum(monitor.protocols?.UDP)} foot="User Datagram Protocol" icon={Zap} color="amber"/></div>
    <Panel className="mt-4 p-5"><div className="flex items-center justify-between"><div className="text-sm font-bold text-white">Capture prerequisites</div><button onClick={()=>setShowGuide(v=>!v)} className="text-xs text-rose-300">{showGuide ? 'Hide' : 'Show'} guide</button></div>{showGuide && <div className="mt-4 space-y-3 text-xs leading-5 text-slate-400"><p><strong className="text-slate-200">Windows:</strong> Install Npcap with WinPcap API-compatible mode enabled, open PowerShell as Administrator, activate your virtual environment and start Django from that terminal.</p><p><strong className="text-slate-200">Laptop visibility:</strong> Capture sees packets visible to the selected adapter. It does not reveal all traffic from every device on a switched Wi-Fi/LAN.</p><p><strong className="text-slate-200">Whole-network visibility:</strong> Use an authorized gateway/router mirror, switch SPAN port or a network TAP. Do not capture networks you do not own or administer.</p><p><strong className="text-slate-200">Feature parity:</strong> Current packet aggregation estimates some CIC features from headers. Validate with CICFlowMeter before relying on its model predictions.</p></div>}</Panel>
  </>
}

function AlertsPage({ events, search, setSearch, onExplain, onAcknowledge, onBlock }) {
  const [severity, setSeverity] = useState('')
  const filtered = events.filter(e => !severity || e.severity === severity)
  return <><SectionTitle eyebrow="Incident queue" title="Threat alerts" description="Review model-flagged flows, investigate contributing features and record analyst acknowledgement." right={<Badge tone="red">{filtered.filter(e=>!e.acknowledged).length} OPEN</Badge>}/><Panel className="overflow-hidden"><div className="flex flex-wrap items-center gap-2 border-b border-slate-800 p-4"><div className="relative min-w-[220px] flex-1"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search IP, attack label or protocol..." className="w-full rounded-xl border border-slate-700 bg-[#111114] py-2.5 pl-9 pr-3 text-xs outline-none focus:border-rose-400"/></div><select value={severity} onChange={e=>setSeverity(e.target.value)} className="rounded-xl border border-slate-700 bg-[#111114] px-3 py-2.5 text-xs text-slate-300"><option value="">All severities</option>{['critical','high','medium','low'].map(s=><option key={s}>{s}</option>)}</select></div><EventsTable rows={filtered} onExplain={onExplain} onAcknowledge={onAcknowledge} onBlock={onBlock}/></Panel></>
}

function ExplainPage({ event, onSelect, events, notify }) {
  const [explainData, setExplainData] = useState(event?.explanation || null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setExplainData(event?.explanation || null) }, [event?.id])
  const run = async () => { if (!event) return; try { setBusy(true); const r = await api.explain(event.id); setExplainData(r); notify('SHAP and LIME explanations generated.') } catch (err) { notify(messageOf(err), 'error') } finally { setBusy(false) } }
  return <><SectionTitle eyebrow="Model transparency" title="Explainable AI" description="Inspect the feature contributions behind an individual LSTM/TCN ensemble prediction."/><div className="grid gap-4 xl:grid-cols-[.8fr_1.2fr]"><Panel className="p-4"><div className="mb-3 text-sm font-bold text-white">Select a network event</div><div className="scrollbar max-h-[490px] space-y-2 overflow-y-auto">{events.slice(0,60).map(e=><button key={e.id} onClick={()=>onSelect(e)} className={cx('w-full rounded-xl border p-3 text-left transition', event?.id===e.id ? 'border-rose-400/40 bg-rose-400/[.07]' : 'border-slate-800 bg-slate-900/35 hover:border-slate-600')}><div className="flex items-center justify-between"><span className="mono text-[10px] text-slate-500">FLOW-{String(e.id).padStart(5,'0')}</span><Severity level={e.severity}/></div><div className="mt-2 text-xs font-semibold text-slate-200">{e.prediction}</div><div className="mono mt-1 text-[10px] text-slate-500">{e.src_ip} → {e.dst_ip}</div></button>)}{!events.length && <EmptyState title="No events to explain" text="Start monitoring or import a PCAP first."/>}</div></Panel>
    <div className="space-y-4"><Panel className="p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-sm font-bold text-white">Prediction investigation</div><div className="mt-1 text-[10px] text-slate-500">{event ? `Flow #${event.id} · ${dateTime(event.timestamp)}` : 'Choose a flow from the left'}</div></div><Button onClick={run} disabled={!event || busy}><BrainCircuit size={14}/>{busy ? 'Explaining…' : 'Generate explanations'}</Button></div>{event && <div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-[9px] uppercase tracking-widest text-slate-500">Prediction</div><div className="mt-1 text-lg font-bold text-white">{event.prediction}</div></div><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-[9px] uppercase tracking-widest text-slate-500">Confidence</div><div className="mt-1 text-lg font-bold text-rose-300">{(event.confidence*100).toFixed(1)}%</div></div><div className="rounded-xl bg-slate-900/70 p-3"><div className="text-[9px] uppercase tracking-widest text-slate-500">Models</div><div className="mt-1 text-sm font-bold text-white">LSTM + TCN</div></div></div>}</Panel>
      <Panel className="p-5"><div className="mb-1 text-sm font-bold text-white">SHAP · Global feature attribution for this flow</div><div className="mb-4 text-[10px] text-slate-500">Gradient-based SHAP values for the loaded LSTM model. Larger absolute values indicate stronger contribution.</div>{explainData?.shap?.length ? <div className="space-y-3">{explainData.shap.map(item=><div key={item.feature}><div className="mb-1 flex justify-between gap-3 text-[10px]"><span className="mono text-slate-300">{item.feature}</span><span className="mono text-slate-500">{item.value.toFixed(4)}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-rose-300" style={{width:`${Math.max(2, item.importance/(explainData.shap[0].importance || 1)*100)}%`}}/></div></div>)}</div> : <EmptyState icon={BrainCircuit} title="SHAP explanation not generated" text="Choose an event and click Generate explanations. SHAP requires TensorFlow, SHAP and a compatible saved LSTM model."/>}</Panel>
      <Panel className="p-5"><div className="mb-1 text-sm font-bold text-white">LIME · Local interpretable explanation</div><div className="mb-4 text-[10px] text-slate-500">Feature conditions that locally influenced the ensemble prediction.</div>{explainData?.lime?.length ? <div className="space-y-2">{explainData.lime.map((item,i)=><div key={i} className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2"><span className="text-xs text-slate-300">{item.feature}</span><span className={cx('mono text-xs font-bold',item.weight>=0?'text-rose-300':'text-emerald-300')}>{item.weight>=0?'+':''}{item.weight.toFixed(4)}</span></div>)}</div> : <EmptyState icon={Fingerprint} title="LIME explanation not generated" text="LIME will perturb the selected flow's feature vector and query the same model ensemble."/>}</Panel></div></div></>
}

function PcapPage({ notify }) {
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const run = async e => { e.preventDefault(); if (!file) return; try { setBusy(true); setResult(await api.pcap(file)); notify('PCAP analysis completed.') } catch (err) { notify(messageOf(err), 'error') } finally { setBusy(false) } }
  return <><SectionTitle eyebrow="Offline forensics" title="PCAP analyzer" description="Import a packet capture, aggregate bidirectional flows and score them with the same IDS models used by the live sensor."/><Panel className="p-5 sm:p-7"><form onSubmit={run}><label className="flex cursor-pointer flex-col items-center rounded-2xl border border-dashed border-slate-600 bg-slate-900/40 px-5 py-12 text-center transition hover:border-rose-400/50 hover:bg-rose-400/[.03]"><div className="mb-3 rounded-2xl bg-rose-400/10 p-4 text-rose-300"><Upload size={23}/></div><div className="text-sm font-bold text-white">Drop a packet capture here</div><div className="mt-1 text-xs text-slate-500">or browse from your computer · .pcap, .pcapng, .cap · up to 100 MB</div><input type="file" accept=".pcap,.pcapng,.cap" className="hidden" onChange={e=>setFile(e.target.files?.[0] || null)}/>{file && <div className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs text-rose-200">{file.name} · {fmtBytes(file.size)}</div>}</label><div className="mt-4 flex justify-end"><Button type="submit" disabled={!file || busy}><FileSearch size={14}/>{busy ? 'Analyzing capture…' : 'Analyze PCAP'}</Button></div></form>{result && <div className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-400/[.05] p-4"><div className="flex items-center gap-2 text-sm font-bold text-emerald-300"><CheckCircle2 size={16}/> Analysis completed</div><div className="mt-3 grid gap-3 sm:grid-cols-3"><div><div className="text-[10px] text-slate-500">Packets read</div><div className="mt-1 text-xl font-bold text-white">{fmtNum(result.packets_read)}</div></div><div><div className="text-[10px] text-slate-500">Flows extracted</div><div className="mt-1 text-xl font-bold text-white">{fmtNum(result.flows_extracted)}</div></div><div><div className="text-[10px] text-slate-500">Events stored</div><div className="mt-1 text-xl font-bold text-rose-300">{fmtNum(result.events_created)}</div></div></div><p className="mt-3 text-[10px] leading-5 text-slate-500">{result.note}</p></div>}</Panel><div className="mt-4 rounded-xl border border-amber-400/15 bg-amber-400/[.04] p-4 text-xs leading-5 text-amber-200"><strong>Forensic note:</strong> Flow feature extraction from packet headers is approximate. Captures containing only a partial flow can be less informative than complete bidirectional sessions.</div></>
}

function IntelPage({ notify }) {
  const [ip, setIp] = useState('')
  const [rep, setRep] = useState(null)
  const [geo, setGeo] = useState(null)
  const [busy, setBusy] = useState('')
  const runRep = async e => { e.preventDefault(); try { setBusy('rep'); setRep(await api.reputation(ip)) } catch (err) { notify(messageOf(err), 'error') } finally { setBusy('') } }
  const runGeo = async e => { e.preventDefault(); try { setBusy('geo'); setGeo(await api.geo(ip)) } catch (err) { notify(messageOf(err), 'error') } finally { setBusy('') } }
  return <><SectionTitle eyebrow="External context" title="Threat intelligence" description="Enrich suspicious IP addresses with reputation reports and approximate GeoIP information."/><Panel className="p-5"><label className="mb-2 block text-[10px] font-bold uppercase tracking-[.16em] text-slate-500">IP address to investigate</label><div className="flex flex-col gap-2 sm:flex-row"><input value={ip} onChange={e=>setIp(e.target.value)} placeholder="e.g. 8.8.8.8" className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-[#111114] px-3 py-3 text-sm outline-none focus:border-rose-400"/><Button onClick={runRep} disabled={!ip || !!busy}><ShieldAlert size={14}/>{busy==='rep'?'Checking…':'IP reputation'}</Button><Button variant="soft" onClick={runGeo} disabled={!ip || !!busy}><Globe2 size={14}/>{busy==='geo'?'Resolving…':'GeoIP lookup'}</Button></div><p className="mt-2 text-[10px] text-slate-600">Private and local IPs are not sent to public reputation providers.</p></Panel><div className="mt-4 grid gap-4 lg:grid-cols-2"><Panel className="p-5"><div className="mb-4 flex items-center gap-2 text-sm font-bold text-white"><ShieldAlert size={16} className="text-rose-300"/>AbuseIPDB reputation</div>{rep ? rep.available ? <div className="space-y-3"><div className="flex items-end justify-between"><div><div className="text-[10px] text-slate-500">Abuse confidence score</div><div className="mt-1 text-3xl font-extrabold text-white">{rep.abuse_confidence_score}%</div></div><Badge tone={rep.abuse_confidence_score>=75?'red':rep.abuse_confidence_score>=30?'amber':'green'}>{rep.abuse_confidence_score>=75?'HIGH RISK':rep.abuse_confidence_score>=30?'REVIEW':'LOW SCORE'}</Badge></div>{[['Reports',rep.total_reports],['ISP',rep.isp],['Country',rep.country_code],['TOR exit node',rep.is_tor?'Yes':'No'],['Last reported',rep.last_reported_at || '—']].map(x=><div key={x[0]} className="flex justify-between border-b border-slate-800 py-2 text-xs"><span className="text-slate-500">{x[0]}</span><span className="text-slate-200">{x[1] ?? '—'}</span></div>)}</div> : <EmptyState icon={LockKeyhole} title="Reputation service not configured" text={rep.message}/> : <EmptyState icon={Globe2} title="No reputation lookup" text="Enter a public IP and configure an AbuseIPDB API key in the backend .env file."/>}</Panel><Panel className="p-5"><div className="mb-4 flex items-center gap-2 text-sm font-bold text-white"><Globe2 size={16} className="text-rose-300"/>GeoIP location</div>{geo ? geo.available ? <div className="space-y-3"><div className="rounded-xl border border-rose-400/15 bg-rose-400/[.05] p-4"><div className="text-[10px] uppercase tracking-widest text-slate-500">Approximate location</div><div className="mt-1 text-xl font-bold text-white">{geo.city || 'Unknown city'}, {geo.country || 'Unknown country'}</div><div className="mt-1 text-xs text-slate-400">{geo.region || ''} · {geo.country_code || ''}</div></div>{[['Latitude',geo.latitude],['Longitude',geo.longitude],['Timezone',geo.timezone]].map(x=><div key={x[0]} className="flex justify-between border-b border-slate-800 py-2 text-xs"><span className="text-slate-500">{x[0]}</span><span className="mono text-slate-200">{x[1] ?? '—'}</span></div>)}</div> : <EmptyState icon={Globe2} title="GeoIP database unavailable" text={geo.message}/> : <EmptyState icon={Globe2} title="No GeoIP lookup" text="Add a MaxMind GeoLite2 City database and configure GEOIP_DB_PATH to enable IP geolocation."/>}</Panel></div></>
}

function TopologyPage() {
  const [data, setData] = useState({nodes:[],edges:[]})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = async () => { try { setBusy(true); setData(await api.topology()); setError('') } catch (e) { setError(messageOf(e)) } finally { setBusy(false) } }
  useEffect(()=>{load()},[])
  const graph = useMemo(()=>{
    const nodes = data.nodes.map((n,i)=>({id:n.id, position:{x:100+(i%4)*220,y:70+Math.floor(i/4)*150}, data:{label:<div className="min-w-[130px] rounded-xl border border-rose-400/25 bg-[#0d1a2b] px-3 py-2 shadow-lg"><div className="flex items-center gap-2 text-[10px] font-bold text-rose-200"><Server size={12}/>{n.local?'LOCAL NODE':'REMOTE HOST'}</div><div className="mono mt-1 text-xs text-slate-100">{n.label}</div><div className="mt-1 text-[9px] text-slate-500">{n.events} observed flows</div></div>},style:{background:'transparent',border:0,padding:0,width:160}}))
    const edges=data.edges.map(e=>({id:e.id,source:e.source,target:e.target,animated:e.attacks>0,style:{stroke:e.attacks>0?'#fb7185':'#F97316',strokeWidth:e.attacks>0?2:1.2},label:e.protocol,labelStyle:{fill:'#64748b',fontSize:9},labelBgStyle:{fill:'#18181D'}}))
    return {nodes,edges}
  },[data])
  return <><SectionTitle eyebrow="Network visibility" title="Network topology" description="A passive map of observed IP endpoints and traffic relationships from recent flows." right={<Button variant="soft" onClick={load} disabled={busy}><RefreshCw size={14}/>{busy?'Refreshing…':'Refresh graph'}</Button>}/>{error && <div className="mb-3 text-xs text-rose-300">{error}</div>}<Panel className="overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3"><div className="text-xs text-slate-400">{data.nodes.length} endpoints · {data.edges.length} observed relationships</div><div className="flex gap-3 text-[10px] text-slate-500"><span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-rose-400"/>Normal flow</span><span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-rose-400"/>Attack flow</span></div></div><div className="h-[560px] bg-[#111114]">{data.nodes.length ? <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView fitViewOptions={{padding:.3}}><Background color="#303038" gap={24}/><Controls/><MiniMap nodeColor={() => '#FB3C5B'} maskColor="rgba(5,9,16,.72)"/></ReactFlow> : <EmptyState icon={Network} title="Topology is empty" text="Start live monitoring or upload a PCAP to create observed endpoints and connections."/>}</div></Panel><p className="mt-3 text-[10px] leading-5 text-slate-600">Topology is derived from observed flow source and destination IPs. It is not an active network discovery scan and does not imply visibility into devices outside the capture point.</p></>
}

function ReportsPage({ notify, block, isAdmin }) {
  const [rules, setRules] = useState([])
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [reportBusy, setReportBusy] = useState(false)
  const load = () => api.rules().then(setRules).catch(e=>notify(messageOf(e),'error'))
  useEffect(()=>{load()},[])
  const download = async () => { try { setReportBusy(true); const blob=await api.report(); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='xids-security-report.pdf'; a.click(); URL.revokeObjectURL(url); notify('PDF report generated.') } catch(e) { notify(messageOf(e),'error') } finally { setReportBusy(false) } }
  const testEmail = async e => { e.preventDefault(); try { setBusy(true); const r=await api.testEmail(email); notify(r.message) } catch(e) { notify(messageOf(e),'error') } finally { setBusy(false) } }
  const doUnblock = async ip => { if (!window.confirm(`Remove X-IDS firewall rules for ${ip}?`)) return; try { await api.unblock(ip); notify(`Unblocked ${ip}.`); load() } catch(e) { notify(messageOf(e),'error') } }
  return <><SectionTitle eyebrow="Response & audit" title="Reports and response" description="Export investigation summaries, test notification delivery and review active firewall actions."/><div className="grid gap-4 lg:grid-cols-2"><Panel className="p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-rose-400/10 p-3 text-rose-300"><FileText size={20}/></div><div><div className="text-sm font-bold text-white">Security report</div><div className="text-[10px] text-slate-500">PDF summary of recent flows and incident counts</div></div></div><Button className="mt-5 w-full" onClick={download} disabled={reportBusy}><Download size={14}/>{reportBusy?'Preparing PDF…':'Download PDF report'}</Button></Panel><Panel className="p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-violet-400/10 p-3 text-violet-300"><Mail size={20}/></div><div><div className="text-sm font-bold text-white">Email delivery test</div><div className="text-[10px] text-slate-500">Verify SMTP configuration from backend .env</div></div></div><form onSubmit={testEmail} className="mt-5 flex gap-2"><input type="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="security@example.com" className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-[#111114] px-3 py-2.5 text-xs outline-none focus:border-rose-400"/><Button type="submit" disabled={busy}>{busy?'Sending…':'Send test'}</Button></form></Panel></div>
    <Panel className="mt-4 overflow-hidden"><div className="flex items-center justify-between border-b border-slate-800 px-5 py-4"><div><div className="text-sm font-bold text-white">Firewall block rules</div><div className="mt-1 text-[10px] text-slate-500">Rules created by X-IDS. Removing a rule requires the backend to have permission.</div></div><Button variant="soft" onClick={load}><RefreshCw size={13}/>Refresh</Button></div>{rules.length ? <div className="divide-y divide-slate-800">{rules.map(r=><div key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"><div><div className="mono text-xs text-slate-200">{r.ip_address}</div><div className="mt-1 text-[10px] text-slate-500">{r.note} · {dateTime(r.created_at)}</div></div><div className="flex items-center gap-2"><Badge tone={r.active?'red':'slate'}>{r.active?'ACTIVE':'REMOVED'}</Badge>{r.active && isAdmin && <Button variant="danger" onClick={()=>doUnblock(r.ip_address)}>Unblock</Button>}</div></div>)}</div> : <EmptyState icon={Lock} title="No firewall rules yet" text="Use Block on a public IP from an alert. Firewall modifications are disabled unless the backend is run with administrator/root privileges."/>}</Panel>
  </>
}

function SettingsPage({ config, setConfigValue, notify, isAdmin }) {
  const [threshold, setThreshold] = useState(config.detection_threshold || 0.85)
  useEffect(()=>setThreshold(config.detection_threshold || 0.85),[config.detection_threshold])
  return <><SectionTitle eyebrow="System policy" title="Configuration" description="Control alert thresholds and optional response automation. Automatic blocking is disabled by default."/><div className="grid gap-4 xl:grid-cols-2"><Panel className="p-5"><div className="mb-4 flex items-center gap-2 text-sm font-bold text-white"><ShieldCheck size={16} className="text-rose-300"/>Detection and response</div>{isAdmin && <div className="flex items-center justify-between gap-4 border-b border-slate-800 py-4"><div><div className="text-xs font-semibold text-slate-200">Automatic IP blocking</div><div className="mt-1 max-w-sm text-[10px] leading-4 text-slate-500">When enabled, high-confidence attack predictions may create firewall rules for public source IPs. Private IPs and allowlisted IPs are never blocked.</div></div><button onClick={()=>setConfigValue({auto_block_enabled:!config.auto_block_enabled})} className={cx('relative h-6 w-11 rounded-full transition',config.auto_block_enabled?'bg-rose-500':'bg-slate-700')}><span className={cx('absolute top-1 h-4 w-4 rounded-full bg-white transition',config.auto_block_enabled?'left-6':'left-1')}/></button></div>}<div className="py-4"><div className="flex items-center justify-between"><div><div className="text-xs font-semibold text-slate-200">Automatic block threshold</div><div className="mt-1 text-[10px] text-slate-500">Minimum ensemble confidence before an automatic block action.</div></div><span className="mono text-sm font-bold text-rose-300">{Math.round(threshold*100)}%</span></div><input type="range" min="0.5" max="1" step="0.01" value={threshold} onChange={e=>setThreshold(Number(e.target.value))} className="mt-4 w-full"/><div className="mt-3 flex justify-between text-[9px] text-slate-600"><span>50% · More sensitive</span><span>100% · More conservative</span></div>{isAdmin && <Button className="mt-4" onClick={()=>setConfigValue({detection_threshold:threshold})}>Save threshold</Button>}</div></Panel>
    <Panel className="p-5"><div className="mb-4 flex items-center gap-2 text-sm font-bold text-white"><Mail size={16} className="text-violet-300"/>Notification policy</div><div className="flex items-center justify-between gap-4 border-b border-slate-800 py-4"><div><div className="text-xs font-semibold text-slate-200">Email alerts</div><div className="mt-1 text-[10px] text-slate-500">Send configured SMTP email notifications for model-flagged threats.</div></div>{isAdmin && <button onClick={()=>setConfigValue({email_alerts_enabled:!config.email_alerts_enabled})} className={cx('relative h-6 w-11 rounded-full transition',config.email_alerts_enabled?'bg-rose-500':'bg-slate-700')}><span className={cx('absolute top-1 h-4 w-4 rounded-full bg-white transition',config.email_alerts_enabled?'left-6':'left-1')}/></button>}</div><div className="mt-4 space-y-3 text-xs"><div className="flex items-center justify-between"><span className="text-slate-500">SMTP credentials</span><Badge tone={config.smtp_configured?'green':'amber'}>{config.smtp_configured?'CONFIGURED':'NOT CONFIGURED'}</Badge></div><div className="flex items-center justify-between"><span className="text-slate-500">AbuseIPDB API</span><Badge tone={config.abuseipdb_configured?'green':'amber'}>{config.abuseipdb_configured?'CONFIGURED':'OPTIONAL'}</Badge></div><div className="flex items-center justify-between"><span className="text-slate-500">MaxMind GeoIP database</span><Badge tone={config.geoip_configured?'green':'amber'}>{config.geoip_configured?'CONFIGURED':'OPTIONAL'}</Badge></div></div></Panel></div><div className="mt-4 rounded-xl border border-amber-400/15 bg-amber-400/[.04] p-4 text-xs leading-5 text-amber-200"><strong>Safe defaults:</strong> Auto-blocking is off by default. Test firewall actions with a known public test IP in a controlled environment, keep a local console session open, and maintain a separate allowlist before enabling automation.</div></>
}

export default App
