import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 30000, withCredentials: true })
const csrfToken = () => {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}
http.interceptors.request.use(config => {
  const method = (config.method || 'get').toLowerCase()
  if (!['get', 'head', 'options', 'trace'].includes(method)) {
    const token = csrfToken()
    if (token) config.headers['X-CSRFToken'] = token
  }
  return config
})

export const api = {
  csrf: () => http.get('/auth/csrf/').then(r => r.data),
  register: data => http.post('/auth/register/', data).then(r => r.data),
  me: () => http.get('/auth/me/').then(r => r.data),
  login: async (username, password) => { await http.get('/auth/csrf/'); return http.post('/auth/login/', { username, password }).then(r => r.data.user) },
  logout: () => http.post('/auth/logout/').then(r => r.data),
  users: () => http.get('/users/').then(r => r.data),
  createUser: data => http.post('/users/', data).then(r => r.data),
  summary: () => http.get('/dashboard/summary/').then(r => r.data),
  events: (params = {}) => http.get('/events/', { params }).then(r => r.data),
  interfaces: () => http.get('/monitor/interfaces/').then(r => r.data),
  monitorStatus: () => http.get('/monitor/status/').then(r => r.data),
  startMonitor: interfaceName => http.post('/monitor/start/', { interface: interfaceName }).then(r => r.data),
  stopMonitor: () => http.post('/monitor/stop/').then(r => r.data),
  explain: id => http.post(`/events/${id}/explain/`).then(r => r.data),
  acknowledge: id => http.post(`/events/${id}/acknowledge/`).then(r => r.data),
  pcap: file => { const data = new FormData(); data.append('pcap_file', file); return http.post('/pcap/analyze/', data, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 }).then(r => r.data) },
  reputation: ip => http.post('/ip/reputation/', { ip }).then(r => r.data),
  geo: ip => http.get('/ip/geo/', { params: { ip } }).then(r => r.data),
  topology: () => http.get('/topology/').then(r => r.data),
  block: ip => http.post('/response/block/', { ip }).then(r => r.data),
  unblock: ip => http.post('/response/unblock/', { ip }).then(r => r.data),
  rules: () => http.get('/response/rules/').then(r => r.data),
  report: () => http.get('/reports/pdf/', { responseType: 'blob' }).then(r => r.data),
  config: () => http.get('/settings/').then(r => r.data),
  updateConfig: data => http.post('/settings/', data).then(r => r.data),
  testEmail: email => http.post('/settings/test-email/', { email }).then(r => r.data),
}

export function connectLive(onEvent, onStatus) {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws/events/`)
  socket.onopen = () => onStatus?.(true)
  socket.onclose = () => onStatus?.(false)
  socket.onerror = () => onStatus?.(false)
  socket.onmessage = e => { try { const msg = JSON.parse(e.data); if (msg.type === 'event') onEvent(msg.data) } catch { /* ignore malformed frame */ } }
  return socket
}
