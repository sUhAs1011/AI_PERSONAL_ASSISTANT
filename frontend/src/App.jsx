import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { chat, submitHitlDecision, getPreferences, putPreferences, getEvents, primeCalendarCache } from './lib/api'
import {
  Calendar,
  ChevronLeft,
  MessageSquare,
  Settings as SettingsIcon,
  ChevronRight,
  Clock,
  AlertTriangle,
  Mic,
  Send,
  Zap,
  LogOut,
} from 'lucide-react'

// --- LOGIN PAGE ---
const LoginPage = ({ onLogin }) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleLogin = (e) => {
    e.preventDefault()
    if (email === 'suhas.karamalaputti@gmail.com' && password === 'suhas123') {
      onLogin()
    } else {
      setError('Invalid credentials.')
    }
  }

  return (
    <div className="min-h-screen bg-[#F7F8FC] flex items-center justify-center p-6 font-sans">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="premium-card p-10 w-full max-w-md shadow-2xl shadow-brand/10 bg-white rounded-[40px] relative overflow-hidden"
      >
        <div className="absolute top-0 left-0 w-full h-2 bg-brand" />
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 bg-brand rounded-[22px] flex items-center justify-center text-white shadow-xl shadow-brand/40">
            <Zap size={32} fill="currentColor" />
          </div>
        </div>
        <h2 className="text-2xl font-black text-slate-900 text-center mb-2 tracking-tight">Welcome Back</h2>
        <p className="text-slate-500 text-center font-medium mb-8 text-sm">Sign in to your intelligent assistant.</p>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-3 block">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={e => { setEmail(e.target.value); setError('') }}
              required
              placeholder="email"
              className="w-full bg-slate-50 border-2 border-slate-50 rounded-2xl px-5 py-4 font-bold text-slate-900 outline-none focus:border-brand/20 transition-all"
            />
          </div>
          <div>
            <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-3 block">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => { setPassword(e.target.value); setError('') }}
              required
              placeholder="password"
              className="w-full bg-slate-50 border-2 border-slate-50 rounded-2xl px-5 py-4 font-bold text-slate-900 outline-none focus:border-brand/20 transition-all"
            />
          </div>
          {error && <p className="text-red-500 text-xs font-bold text-center animate-in fade-in">{error}</p>}
          <button type="submit" className="w-full bg-brand text-white font-black py-4 rounded-2xl shadow-xl shadow-brand/30 hover:scale-[1.02] active:scale-[0.98] transition-all pt-4">
            Sign In
          </button>
        </form>
      </motion.div>
    </div>
  )
}

// --- CHAT PAGE ---
const ChatPage = ({ messages, setMessages, conversationHistory, setConversationHistory }) => {
  const userId = 'u1'
  const [inputText, setInputText] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  useEffect(() => {
    if (typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = false
      recognitionRef.current.interimResults = true

      recognitionRef.current.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(result => result[0])
          .map(result => result.transcript)
          .join('')
        setInputText(transcript)
      }

      recognitionRef.current.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error', event.error)
        setIsListening(false)
      }
    }
  }, [])

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop()
    } else {
      setIsListening(true)
      recognitionRef.current?.start()
    }
  }

  const handleSend = async () => {
    const message = inputText.trim()
    if (!message || isSending) return

    setMessages((prev) => [...prev, { type: 'user', content: message }])
    setInputText('')
    setIsSending(true)

    try {
      const response = await chat({
        user_id: userId,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        message,
        conversation_history: conversationHistory,
      })

      setConversationHistory(response.conversation_history || [])

      if (response.status === 'needs_hitl') {
        setMessages((prev) => [
          ...prev,
          {
            type: 'conflict',
            content: {
              title: 'Schedule Conflict',
              msg: response.summary || 'There is a scheduling conflict.',
              hitlActionId: response.hitl_action_id,
              alternatives: response.alternatives || [],
            },
          },
        ])
      } else {
        const safeSummary = response.summary || 'I need one more detail to help with that.'
        const meetSuffix = response.meet_link ? ` Meet: ${response.meet_link}` : ''
        const inviteSuffix = response.invite_status ? ` Invite: ${response.invite_status}` : ''
        setMessages((prev) => [
          ...prev,
          { type: 'ai', content: `${safeSummary}${inviteSuffix}${meetSuffix}` },
        ])
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { type: 'ai', content: "I couldn't reach the calendar service right now. Want me to retry?" },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-160px)]">
      <div className="flex-1 space-y-8 overflow-y-auto pr-4 custom-scrollbar pb-10">
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`flex ${m.type === 'user' ? 'justify-end' : 'justify-start'} gap-5`}
          >
            {m.type === 'ai' || m.type === 'conflict' ? (
              <div className="w-10 h-10 bg-brand rounded-2xl flex items-center justify-center text-white shrink-0 shadow-lg shadow-brand/20">
                <Zap size={20} fill="currentColor" />
              </div>
            ) : null}

            <div className={`${m.type === 'user' ? 'bg-brand text-white rounded-[28px] rounded-tr-none px-8 py-5' : m.type === 'ai' ? 'premium-card p-8' : 'premium-card overflow-hidden'} max-w-[80%] shadow-xl shadow-slate-100/50`}>
              {m.type === 'conflict' ? (
                <>
                  <div className="bg-red-50 p-6 flex items-center gap-5 border-b border-red-100/30">
                    <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-red-500 shrink-0">
                      <AlertTriangle size={24} />
                    </div>
                    <div>
                      <h4 className="font-bold text-red-900 text-base">{m.content.title}</h4>
                      <p className="text-xs text-red-500 font-bold mt-1">{m.content.msg}</p>
                    </div>
                  </div>
                  <div className="p-8">
                    <span className="text-[11px] font-black text-slate-400 uppercase tracking-[0.2em] mb-6 block">Suggested Alternatives</span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                      {(m.content.alternatives || []).map((alt, j) => (
                        <button
                          key={alt.start_iso || j}
                          onClick={async () => {
                            try {
                              const result = await submitHitlDecision({
                                actionId: m.content.hitlActionId,
                                decision: 'reschedule',
                                selectedStartIso: alt.start_iso,
                              })
                              setMessages((prev) => [
                                ...prev,
                                { type: 'ai', content: result.summary || `Rescheduled to ${alt.start_iso}` },
                              ])
                            } catch {
                              setMessages((prev) => [
                                ...prev,
                                { type: 'ai', content: 'Failed to submit HITL decision.' },
                              ])
                            }
                          }}
                          className="bg-slate-50 p-5 rounded-[24px] text-left flex items-center gap-4 cursor-pointer hover:bg-brand/5 border-2 border-transparent hover:border-brand/10 transition-all group"
                        >
                          <div className="w-12 h-12 rounded-2xl bg-brand/10 flex items-center justify-center text-brand">
                            <Clock size={20} />
                          </div>
                          <div className="flex-1">
                            <h5 className="font-bold text-slate-900 text-sm">{alt.label || 'Suggested Slot'}</h5>
                            <p className="text-[11px] font-bold text-slate-400 mt-1">{alt.start_iso || 'Alternative time'}</p>
                          </div>
                          <ChevronRight size={16} className="text-slate-300 group-hover:text-brand" />
                        </button>
                      ))}
                    </div>
                    <button className="w-full bg-slate-100 text-slate-600 font-bold py-5 rounded-[24px] text-[15px]">
                      Pick one slot above
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-[15px] font-medium leading-relaxed">{m.content}</p>
                  {m.options && (
                    <div className="flex flex-wrap gap-3 mt-8">
                      {m.options.map(opt => (
                        <button key={opt} className="bg-slate-50 border-2 border-slate-50 px-8 py-3 rounded-2xl text-sm font-bold text-slate-900 hover:border-brand hover:bg-brand/5 transition-all">{opt}</button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        ))}
        {isSending && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex justify-start gap-5`}
          >
            <div className="w-10 h-10 bg-brand rounded-2xl flex items-center justify-center text-white shrink-0 shadow-lg shadow-brand/20">
              <Zap size={20} fill="currentColor" />
            </div>
            <div className="premium-card p-6 max-w-[80%] shadow-xl shadow-slate-100/50 flex items-center gap-1.5 min-h-[50px]">
              <motion.div className="w-2 h-2 rounded-full bg-slate-300" animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.6, ease: "easeInOut", delay: 0 }} />
              <motion.div className="w-2 h-2 rounded-full bg-slate-300" animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.6, ease: "easeInOut", delay: 0.2 }} />
              <motion.div className="w-2 h-2 rounded-full bg-slate-300" animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.6, ease: "easeInOut", delay: 0.4 }} />
            </div>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="mt-8 bg-white border border-slate-100 p-4 rounded-[32px] flex items-center gap-4 shadow-2xl shadow-slate-200/50 max-w-4xl mx-auto w-full relative">
        <button
          onClick={toggleListening}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${isListening ? 'bg-red-50 text-red-500 animate-pulse' : 'text-slate-400 hover:text-brand hover:bg-brand/5'}`}
        >
          {isListening ? <Mic size={22} fill="currentColor" /> : <Mic size={22} />}
        </button>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder={isListening ? "Listening..." : "Message SmartOwner AI..."}
          className="flex-1 bg-transparent border-none outline-none text-base font-medium"
        />
        <button
          onClick={handleSend}
          disabled={isSending}
          className="w-12 h-12 bg-brand text-white rounded-full flex items-center justify-center shadow-xl shadow-brand/30 transition-transform active:scale-90 flex-shrink-0 disabled:opacity-60"
        >
          <Send size={22} fill="currentColor" className="ml-1" />
        </button>
        {isListening && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute -top-12 left-6 bg-red-500 text-white text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-widest shadow-lg"
          >
            Recording
          </motion.div>
        )}
      </div>
    </div>
  )
}

// --- DASHBOARD PAGE ---
const DashboardPage = () => {
  const userId = 'u1'
  const [selectedDate, setSelectedDate] = useState(new Date())
  const [events, setEvents] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchEvents = async (date) => {
    setIsLoading(true)
    setError('')
    try {
      const start = new Date(date)
      start.setHours(0, 0, 0, 0)
      const end = new Date(date)
      end.setHours(23, 59, 59, 999)
      
      const payload = await getEvents(userId, start.toISOString(), end.toISOString())
      setEvents(payload.events || [])
    } catch {
      setError('Failed to load events')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents(selectedDate)
  }, [selectedDate])

  const nextDay = () => setSelectedDate(new Date(selectedDate.getTime() + 86400000))
  const prevDay = () => setSelectedDate(new Date(selectedDate.getTime() - 86400000))
  const goToday = () => setSelectedDate(new Date())

  return (
    <div className="animate-in fade-in slide-in-from-right-4 duration-500">
      <div className="flex flex-col items-center justify-center mb-10">
        <div className="flex items-center gap-6">
          <button onClick={prevDay} className="w-12 h-12 flex items-center justify-center rounded-2xl bg-white shadow-sm hover:shadow-md border border-slate-100 text-slate-400 hover:text-brand transition-all hover:-translate-x-1">
            <ChevronLeft size={24} />
          </button>
          <div className="text-center min-w-[280px]">
            <h2 className="text-4xl font-black text-slate-900 tracking-tight mb-2">
              {selectedDate.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}
            </h2>
            <button onClick={goToday} className="text-[13px] font-bold text-slate-400 uppercase tracking-widest hover:text-brand transition-colors">
              • Jump to Today •
            </button>
          </div>
          <button onClick={nextDay} className="w-12 h-12 flex items-center justify-center rounded-2xl bg-white shadow-sm hover:shadow-md border border-slate-100 text-slate-400 hover:text-brand transition-all hover:translate-x-1">
            <ChevronRight size={24} />
          </button>
        </div>
      </div>
      
      <div className="premium-card p-6 min-h-[500px] relative overflow-hidden bg-white">
        {isLoading && (
          <div className="absolute inset-0 bg-white/50 backdrop-blur-sm z-10 flex items-center justify-center">
             <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin shadow-xl"></div>
          </div>
        )}
        {error && <p className="text-red-500 font-bold mb-4">{error}</p>}
        
        <div className="space-y-4 relative z-0">
           {events.length === 0 && !isLoading && !error && (
             <div className="text-center py-32 text-slate-400 font-bold text-lg">No events scheduled. Enjoy your free time! 🎉</div>
           )}
           {events.map((ev, i) => {
              const startIso = ev.start?.dateTime || ev.start?.date || ev.start_iso
              const endIso = ev.end?.dateTime || ev.end?.date || ev.end_iso
              const start = new Date(startIso || Date.now())
              const end = new Date(endIso || Date.now())
              const timeStr = `${start.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - ${end.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`
              const hasMeet = !!ev.meet_link || !!ev.hangoutLink
              const meetUrl = ev.meet_link || ev.hangoutLink
              const title = ev.title || ev.summary || "Untitled Event"
              
              return (
                <motion.div 
                  key={ev.id || i}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex bg-brand/5 border-l-4 border-brand rounded-2xl p-6 hover:-translate-y-1 hover:shadow-lg transition-all"
                >
                  <div className="flex-1">
                    <h4 className="font-primary font-black text-slate-900 text-xl tracking-tight">{title}</h4>
                    <p className="text-sm text-slate-500 mt-2 font-bold flex items-center gap-2"><Clock size={16} />{timeStr}</p>
                  </div>
                  {hasMeet && (
                    <div className="flex items-center shrink-0">
                      <a href={meetUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 bg-white text-brand px-5 py-3 rounded-xl shadow-sm text-sm font-black hover:bg-brand hover:text-white transition-colors">
                        Join Call <Zap size={16} fill="currentColor" />
                      </a>
                    </div>
                  )}
                </motion.div>
              )
           })}
        </div>
      </div>
    </div>
  )
}

// --- PREFERENCES PAGE ---
const PreferencesPage = () => {
  const userId = 'u1'
  const [noMeetingsBeforeHour, setNoMeetingsBeforeHour] = useState(9)
  const [prefStatus, setPrefStatus] = useState('')

  useEffect(() => {
    const loadPrefs = async () => {
      try {
        const prefs = await getPreferences(userId)
        if (typeof prefs.no_meetings_before_hour === 'number') {
          setNoMeetingsBeforeHour(prefs.no_meetings_before_hour)
        }
      } catch {
        setPrefStatus('Failed to load preferences')
      }
    }
    loadPrefs()
  }, [])

  const savePrefs = async () => {
    try {
      await putPreferences(userId, { no_meetings_before_hour: noMeetingsBeforeHour })
      setPrefStatus('Preferences saved')
    } catch {
      setPrefStatus('Failed to save preferences')
    }
  }

  return (
    <div className="animate-in fade-in slide-in-from-right-4 duration-500">
      <div className="mb-10">
        <h2 className="text-3xl font-black text-slate-900 mb-3 tracking-tight">Preferences</h2>
        <p className="text-[15px] text-slate-500 leading-relaxed font-medium max-w-md">Fine-tune your availability and habits for maximum productivity.</p>
      </div>

      <div className="premium-card p-6 mb-8 max-w-2xl">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h3 className="font-bold text-slate-900">No Meetings Before</h3>
            <p className="text-sm text-slate-500">Used by the backend to avoid morning meetings.</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={noMeetingsBeforeHour}
              onChange={(e) => setNoMeetingsBeforeHour(Number(e.target.value))}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 font-semibold"
            >
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {String(h).padStart(2, '0')}:00
                </option>
              ))}
            </select>
            <button
              onClick={savePrefs}
              className="bg-brand text-white font-bold px-5 py-2 rounded-xl"
            >
              Save
            </button>
          </div>
        </div>
        {prefStatus && <p className="text-xs text-slate-500 mt-3">{prefStatus}</p>}
      </div>
    </div>
  )
}

// --- MAIN APP COMPONENT ---
function App() {
  const userId = 'u1'
  const [isLoggedIn, setIsLoggedIn] = useState(() => localStorage.getItem('auth_token') === 'logged_in')
  const [activeTab, setActiveTab] = useState('chat')
  const [chatMessages, setChatMessages] = useState([
    { type: 'ai', content: 'I can help you book, reschedule, or check availability. Try: "Book a design review tomorrow at 3 PM with alex@example.com".' }
  ])
  const [chatHistory, setChatHistory] = useState([])

  useEffect(() => {
    if (!isLoggedIn) return
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    primeCalendarCache(userId, timezone).catch((err) => {
      console.warn('calendar cache prime failed', err)
    })
  }, [isLoggedIn])

  const handleLogin = () => {
    localStorage.setItem('auth_token', 'logged_in')
    setIsLoggedIn(true)
  }

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    setIsLoggedIn(false)
  }

  if (!isLoggedIn) {
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <div className="flex min-h-screen bg-[#F7F8FC] transition-colors duration-500 font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-[100px] lg:w-[280px] h-screen glass-sidebar flex flex-col items-center lg:items-start py-10 px-6 fixed left-0 top-0 z-50">
        <div className="flex items-center gap-4 mb-20 lg:px-4">
          <motion.div
            whileHover={{ rotate: 15 }}
            className="w-14 h-14 bg-brand rounded-[22px] flex items-center justify-center text-white shadow-2xl shadow-brand/40 group relative"
          >
            <Zap size={28} fill="currentColor" />
          </motion.div>
          <div className="hidden lg:block">
            <h1 className="text-xl font-black text-slate-900 leading-none tracking-tighter">SmartOwner</h1>
            <p className="text-[10px] font-black text-brand uppercase tracking-[0.4em] mt-1">Intelligence</p>
          </div>
        </div>

        <nav className="flex-1 w-full space-y-4">
          {[
            { id: 'chat', label: 'Chat Assistant', icon: MessageSquare },
            { id: 'schedule', label: 'My Schedule', icon: Calendar },
            { id: 'settings', label: 'Preferences', icon: SettingsIcon },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-4 p-4 rounded-[22px] transition-all duration-300 relative group`}
            >
              {activeTab === item.id && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 bg-brand rounded-[22px] shadow-xl shadow-brand/20 -z-10"
                />
              )}
              <item.icon size={22} className={`${activeTab === item.id ? 'text-white' : 'text-slate-400 group-hover:text-brand'} transition-colors`} />
              <span className={`hidden lg:block text-sm font-bold tracking-tight ${activeTab === item.id ? 'text-white' : 'text-slate-400 group-hover:text-brand'}`}>
                {item.label}
              </span>
            </button>
          ))}
        </nav>

        <div className="mt-auto w-full space-y-8">
          <div className="p-4 bg-white border border-slate-100 shadow-sm rounded-[24px] flex items-center gap-3 group relative cursor-pointer hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-2xl bg-brand/10 text-brand flex items-center justify-center shrink-0 border-2 border-white">
              <span className="font-black text-lg">S</span>
            </div>
            <div className="hidden lg:block flex-1 min-w-0">
              <h4 className="font-bold text-slate-900 text-sm truncate">Suhas K.</h4>
              <p className="text-[10px] font-bold text-slate-400 truncate uppercase mt-0.5">Admin</p>
            </div>
            <button
              onClick={handleLogout}
              className="absolute right-4 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-600 transition-opacity bg-red-50 w-8 h-8 rounded-full flex items-center justify-center shadow-lg"
              title="Log out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 ml-[100px] lg:ml-[280px] p-10 lg:p-16 lg:px-20 max-w-[1500px] mx-auto min-h-screen pb-32">
        <header className="flex justify-between items-center mb-10 px-2">
          <div>
            <motion.span
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-[11px] font-black text-brand uppercase tracking-[0.3em] mb-2 block"
            >Welcome Back</motion.span>
            <motion.h2
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-4xl font-black text-slate-900 tracking-tight"
            >What can I do for you <span className="text-brand">today?</span></motion.h2>
          </div>
        </header>

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            {activeTab === 'settings' && <PreferencesPage />}
            {activeTab === 'schedule' && <DashboardPage />}
            {activeTab === 'chat' && <ChatPage messages={chatMessages} setMessages={setChatMessages} conversationHistory={chatHistory} setConversationHistory={setChatHistory} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}

export default App
