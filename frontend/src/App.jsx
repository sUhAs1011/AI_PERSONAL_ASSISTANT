import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Calendar,
  MessageSquare,
  History,
  Settings as SettingsIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  AlertTriangle,
  Coffee,
  Search,
  Mic,
  Send,
  Plus,
  Zap,
  CheckCircle2,
  Bell,
  User,
  Trash2,
  X
} from 'lucide-react'

// --- SHARED COMPONENTS ---
const Toggle = ({ on, toggle }) => (
  <div
    onClick={toggle}
    className={`w-12 h-6 rounded-full relative cursor-pointer transition-colors duration-300 ${on ? 'bg-brand' : 'bg-slate-200 shadow-inner'}`}
  >
    <motion.div
      initial={false}
      animate={{ x: on ? 28 : 4 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className="absolute top-1 w-4 h-4 rounded-full bg-white shadow-md"
    />
  </div>
)

// --- DASHBOARD COMPONENTS ---
// --- DASHBOARD COMPONENTS ---
const CalendarStrip = ({ selectedDate, onSelectDate }) => {
  const [currentDate, setCurrentDate] = useState(new Date())

  const getWeekDates = () => {
    const startOfWeek = new Date(currentDate)
    const day = startOfWeek.getDay()
    const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1) // Adjust for Monday start
    startOfWeek.setDate(diff)

    return Array.from({ length: 9 }, (_, i) => {
      const d = new Date(startOfWeek)
      d.setDate(startOfWeek.getDate() + i)
      return {
        day: ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'][d.getDay()],
        date: d.getDate(),
        id: d.toDateString(),
        isToday: d.toDateString() === new Date().toDateString()
      }
    })
  }

  const weekDates = getWeekDates()
  const monthYear = currentDate.toLocaleString('default', { month: 'long', year: 'numeric' })
  const selectedDateObj = weekDates.find(d => d.date === selectedDate) || weekDates[0]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="premium-card p-6 mb-6"
    >
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900 leading-none">{monthYear}</h2>
          <p className="text-sm font-medium text-slate-400 mt-1 uppercase tracking-wider">
            {new Date().toLocaleDateString('default', { weekday: 'long', month: 'short', day: 'numeric' })}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              const prev = new Date(currentDate)
              prev.setDate(prev.getDate() - 7)
              setCurrentDate(prev)
            }}
            className="p-2 hover:bg-slate-50 rounded-xl transition-colors text-slate-400 hover:text-brand"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => {
              const next = new Date(currentDate)
              next.setDate(next.getDate() + 7)
              setCurrentDate(next)
            }}
            className="p-2 hover:bg-slate-50 rounded-xl transition-colors text-slate-400 hover:text-brand"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
      <div className="flex justify-between gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {weekDates.map((d, i) => (
          <div key={i} className="flex flex-col items-center gap-3 min-w-[50px]">
            <span className={`text-[10px] font-bold tracking-wider font-sans uppercase ${d.isToday ? 'text-brand' : 'text-slate-400'}`}>
              {d.day}
            </span>
            <motion.div
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onSelectDate(d.date)}
              className={`w-[48px] h-[64px] flex flex-col items-center justify-center rounded-[20px] transition-all relative cursor-pointer group ${selectedDate === d.date ? 'bg-brand text-white shadow-[0_8px_20px_rgba(93,95,239,0.3)]' : 'text-slate-900 bg-white hover:bg-slate-50'}`}
            >
              <span className="text-lg font-bold">{d.date}</span>
              {d.isToday && !(selectedDate === d.date) && <div className="w-1 h-1 rounded-full absolute bottom-2 bg-brand" />}
              {selectedDate === d.date && <motion.div layoutId="calendar-active" className="w-1 h-1 rounded-full bg-white absolute bottom-2" />}
            </motion.div>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

const Heatmap = () => (
  <motion.div
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ delay: 0.1 }}
    className="mb-8"
  >
    <div className="flex justify-between items-center mb-4 px-1">
      <h3 className="text-lg font-bold text-slate-900">Schedule Heatmap</h3>
      <div className="flex gap-4">
        <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-[#F8D7DA]" /><span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Busy</span></div>
        <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-[#D1E7DD]" /><span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Free</span></div>
        <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-[#E2E3FF]" /><span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">AI Suggested</span></div>
      </div>
    </div>
    <div className="premium-card p-6">
      <div className="flex h-[120px] gap-2">
        <div className="flex-1 bg-[#D1E7DD]/30 border border-[#D1E7DD] rounded-[18px] flex items-center justify-center text-xs font-bold text-[#198754]">08:00 AM</div>
        <div className="flex-[1.5] bg-[#F8D7DA]/30 border border-[#F8D7DA] rounded-[18px] flex items-center justify-center text-xs font-bold text-[#DC3545]">10:00 AM</div>
        <div className="flex-1 bg-brand/5 border border-brand/20 rounded-[18px] flex flex-col items-center justify-center text-xs font-bold text-brand">
          <Zap size={14} fill="currentColor" className="mb-1" />
          <span>13:00 PM</span>
        </div>
        <div className="flex-[0.5] bg-[#F8D7DA]/30 border border-[#F8D7DA] rounded-[18px] flex items-center justify-center text-xs font-bold text-[#DC3545]">15:00 PM</div>
        <div className="flex-[2] bg-[#D1E7DD]/30 border border-[#D1E7DD] rounded-[18px] flex items-center justify-center text-xs font-bold text-[#198754]">16:00 - 20:00</div>
      </div>
    </div>
  </motion.div>
)

const InsightCard = ({ title, description, icon: Icon, color, label }) => (
  <motion.div
    whileHover={{ x: 5 }}
    className="premium-card p-5 flex gap-5 items-start relative overflow-hidden group transition-all duration-300"
  >
    <div className="absolute top-0 left-0 w-1.5 h-full" style={{ backgroundColor: color }} />
    <div className="w-14 h-14 rounded-[20px] flex items-center justify-center shrink-0 shadow-sm" style={{ backgroundColor: `${color}10`, color: color }}>
      <Icon size={24} />
    </div>
    <div className="flex-1">
      <div className="flex justify-between items-center mb-1.5">
        <h4 className="font-bold text-slate-900 text-base">{title}</h4>
        {label && <span className="text-[9px] font-black uppercase tracking-widest bg-emerald-100 text-emerald-600 px-2.5 py-1 rounded-full">{label}</span>}
      </div>
      <p className="text-[13px] text-slate-500 leading-relaxed font-medium" dangerouslySetInnerHTML={{ __html: description }}></p>
    </div>
  </motion.div>
)

// --- DASHBOARD PAGE ---
const DashboardPage = () => {
  const [selectedDate, setSelectedDate] = useState(new Date().getDate())
  const [isOptimizing, setIsOptimizing] = useState(false)

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <div className="xl:col-span-2 space-y-8">
          <CalendarStrip selectedDate={selectedDate} onSelectDate={setSelectedDate} />
          <Heatmap />

          <div className="animate-in fade-in slide-in-from-bottom-5 duration-700">
            <div className="flex items-center gap-3 mb-6 px-1">
              <div className="w-1.5 h-6 bg-brand rounded-full" />
              <h3 className="text-xl font-bold text-slate-900">AI Weekly Insights</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <InsightCard
                title="Peak Performance Rule"
                description="You prefer meetings after <span class='text-slate-900 font-bold'>10 AM</span>. I've blocked your early morning for deep focus."
                icon={Clock}
                color="#5D5FEF"
              />
              <InsightCard
                title="Suggested Break"
                label="OPTIMAL"
                description="Suggested break at <span class='text-slate-900 font-bold'>2 PM</span>. You usually experience a productivity dip during this window."
                icon={Coffee}
                color="#10B981"
              />
            </div>
          </div>
        </div>

        <div className="space-y-8 animate-in fade-in slide-in-from-right-5 duration-700">
          <div className="bg-brand rounded-[32px] p-8 text-white relative overflow-hidden shadow-2xl shadow-brand/20 min-h-[340px] flex flex-col justify-between">
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-6 text-white/80">
                <Zap size={14} fill="currentColor" />
                <span className="text-[11px] font-black uppercase tracking-[0.2em]">Auto-Optimization</span>
              </div>
              <h2 className="text-3xl font-bold leading-tight mb-4 tracking-tight">Ready to re-align your week?</h2>
              <p className="text-[15px] text-white/80 mb-8 leading-relaxed">I can automatically shift 3 low-priority tasks to tomorrow.</p>
            </div>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => {
                setIsOptimizing(true);
                setTimeout(() => setIsOptimizing(false), 2000);
              }}
              className={`bg-white text-brand font-bold py-4 px-10 rounded-2xl text-[15px] w-full relative z-10 shadow-xl transition-all ${isOptimizing ? 'opacity-50 cursor-wait' : ''}`}
            >
              {isOptimizing ? 'Optimizing...' : 'Optimize Now'}
            </motion.button>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
              className="absolute top-[-40px] right-[-40px] opacity-10"
            >
              <Zap size={260} />
            </motion.div>
          </div>

          <div className="premium-card p-8">
            <div className="flex justify-between items-start mb-8">
              <div>
                <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest">Efficiency Focus Score</span>
                <div className="text-[56px] font-black text-slate-900 leading-none mt-2">84<span className="text-lg text-slate-300 font-bold ml-1">/100</span></div>
              </div>
            </div>
            <div className="flex items-end gap-2 h-24 w-full mb-6">
              {[40, 60, 30, 20, 70, 95, 45, 60, 80, 55].map((h, i) => (
                <motion.div
                  key={i}
                  initial={{ height: 0 }}
                  animate={{ height: `${h}%` }}
                  transition={{ delay: i * 0.05, duration: 1 }}
                  className={`flex-1 rounded-full ${i === 5 ? 'bg-brand' : 'bg-brand/20'}`}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// --- CHAT PAGE ---
const ChatPage = () => {
  const [inputText, setInputText] = useState('')
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef(null)

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

  const messages = [
    { type: 'user', content: 'Schedule a meeting with the design team for tomorrow afternoon.' },
    { type: 'ai', content: "I've scanned your calendar for tomorrow. Here are some open slots that work for everyone on the design team:", options: ['2:00 PM', '3:30 PM', '4:15 PM'] },
    { type: 'user', content: "Let's do 3:00 PM instead, I need to leave early." },
    { type: 'conflict', content: { title: 'Schedule Conflict', msg: 'You already have a meeting at 3 PM (Weekly Sync).' } }
  ]

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
                      {[
                        { label: 'Reschedule Weekly Sync', sub: 'Move to Friday at 10:00 AM', icon: Calendar },
                        { label: 'Earlier Slot: 1:30 PM', sub: 'Both parties are available', icon: Clock },
                      ].map((item, j) => (
                        <div key={j} className="bg-slate-50 p-5 rounded-[24px] flex items-center gap-4 cursor-pointer hover:bg-brand/5 border-2 border-transparent hover:border-brand/10 transition-all group">
                          <div className="w-12 h-12 rounded-2xl bg-brand/10 flex items-center justify-center text-brand">
                            <item.icon size={20} />
                          </div>
                          <div className="flex-1">
                            <h5 className="font-bold text-slate-900 text-sm">{item.label}</h5>
                            <p className="text-[11px] font-bold text-slate-400 mt-1">{item.sub}</p>
                          </div>
                          <ChevronRight size={16} className="text-slate-300 group-hover:text-brand" />
                        </div>
                      ))}
                    </div>
                    <button className="w-full bg-brand text-white font-bold py-5 rounded-[24px] text-[15px] shadow-2xl shadow-brand/30">
                      Approve Suggestion
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
          placeholder={isListening ? "Listening..." : "Message SmartOwner AI..."}
          className="flex-1 bg-transparent border-none outline-none text-base font-medium"
        />
        <button className="w-12 h-12 bg-brand text-white rounded-full flex items-center justify-center shadow-xl shadow-brand/30 transition-transform active:scale-90 flex-shrink-0">
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

// --- PREFERENCES PAGE ---
const PreferencesPage = () => {
  const [duration, setDuration] = useState(0)
  const [paddingType, setPaddingType] = useState('pre')
  const [aiScheduling, setAiScheduling] = useState(true)
  const [ranges, setRanges] = useState([
    { label: 'Morning Deep Work', time: '08:00 AM - 10:00 AM', on: true, icon: '☀️' },
    { label: 'Lunch Reset', time: '12:30 PM - 01:30 PM', on: true, icon: '🍴' },
    { label: 'Post-Work Calm', time: '05:30 PM - 07:00 PM', on: false, icon: '🌙' },
  ])

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newRange, setNewRange] = useState({ label: '', time: '', icon: '📅' })

  const labels = [0, 15, 30, 45, 60, 90, 120]
  const trackRef = useRef(null)

  const toggleRange = (index) => {
    const newRanges = [...ranges]
    newRanges[index].on = !newRanges[index].on
    setRanges(newRanges)
  }

  const deleteRange = (index) => {
    const newRanges = ranges.filter((_, i) => i !== index)
    setRanges(newRanges)
  }

  const handleAddRange = () => {
    if (newRange.label && newRange.time) {
      setRanges([...ranges, { ...newRange, on: true }])
      setNewRange({ label: '', time: '', icon: '📅' })
      setIsModalOpen(false)
    }
  }

  const handleDrag = (event, info) => {
    if (!trackRef.current) return
    const rect = trackRef.current.getBoundingClientRect()
    const x = Math.min(Math.max(info.point.x - rect.left, 0), rect.width)
    const percent = x / rect.width
    const value = Math.round(percent * 120) // Continuous 0-120
    if (value !== duration) {
      setDuration(value)
    }
  }

  return (
    <div className="animate-in fade-in slide-in-from-right-4 duration-500">
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="absolute inset-0 bg-slate-900/60 backdrop-blur-md"
            />
            <motion.div 
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="bg-white rounded-[40px] p-10 w-full max-w-md relative z-10 shadow-2xl"
            >
              <div className="flex justify-between items-center mb-8">
                <h3 className="text-2xl font-black text-slate-900 tracking-tight">Add New Range</h3>
                <button 
                  onClick={() => setIsModalOpen(false)}
                  className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-3 block">Range Name</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Afternoon Focus"
                    value={newRange.label}
                    onChange={(e) => setNewRange({...newRange, label: e.target.value})}
                    className="w-full bg-slate-50 border-2 border-slate-50 rounded-[20px] px-6 py-4 font-bold text-slate-900 outline-none focus:border-brand/20 transition-all"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-3 block">Time Window</label>
                  <input 
                    type="text" 
                    placeholder="e.g. 02:00 PM - 04:00 PM"
                    value={newRange.time}
                    onChange={(e) => setNewRange({...newRange, time: e.target.value})}
                    className="w-full bg-slate-50 border-2 border-slate-50 rounded-[20px] px-6 py-4 font-bold text-slate-900 outline-none focus:border-brand/20 transition-all"
                  />
                </div>
                
                <button 
                  onClick={handleAddRange}
                  className="w-full bg-brand text-white font-black py-5 rounded-[24px] text-[15px] shadow-2xl shadow-brand/30 mt-4 hover:scale-[1.02] active:scale-[0.98] transition-all"
                >
                  Confirm Range
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="mb-10">
        <h2 className="text-3xl font-black text-slate-900 mb-3 tracking-tight">Preferences</h2>
        <p className="text-[15px] text-slate-500 leading-relaxed font-medium max-w-md">Fine-tune your availability and habits for maximum productivity.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-8">
          <div className="premium-card p-8">
            <div className="flex justify-between items-start mb-16">
              <div>
                <h3 className="font-bold text-slate-900 text-xl">Preferred meeting duration</h3>
                <p className="text-sm text-slate-400 font-medium mt-2 leading-relaxed max-w-[240px]">SmartOwner AI will suggest times matching this length.</p>
              </div>
              <motion.div
                key={duration}
                initial={{ y: 5, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="bg-brand/10 text-brand px-5 py-6 rounded-[24px] flex flex-col items-center min-w-[80px]"
              >
                <span className="text-3xl font-black leading-none mb-1">{duration}</span>
                <span className="text-[10px] font-black uppercase tracking-widest">min</span>
              </motion.div>
            </div>

            <div className="px-4">
              <div ref={trackRef} className="relative h-2 bg-slate-100 rounded-full mb-12">
                {/* Tick Marks for major labels */}
                <div className="absolute inset-0 flex justify-between">
                  {labels.map(v => (
                    <div key={v} className="w-1.5 h-2 bg-white/50 rounded-full" />
                  ))}
                </div>

                <motion.div
                  className="absolute h-full bg-brand rounded-full"
                  animate={{ width: `${(duration / 120) * 100}%` }}
                  transition={{ type: "tween", duration: 0.1 }}
                />

                <motion.div
                  drag="x"
                  dragMomentum={false}
                  dragConstraints={trackRef}
                  dragElastic={0}
                  onDrag={handleDrag}
                  animate={{ x: `${(duration / 120) * (trackRef.current?.offsetWidth || 0)}px` }}
                  transition={{ type: "tween", duration: 0.1 }}
                  style={{ x: 0, left: 0 }}
                  className="absolute -top-3 -ml-4 w-8 h-8 rounded-full bg-brand border-[6px] border-white shadow-[0_10px_25px_rgba(93,95,239,0.4)] cursor-grab active:cursor-grabbing z-20"
                />

                <div className="absolute top-8 inset-x-0 flex justify-between px-2">
                  {labels.map(v => (
                    <span
                      key={v}
                      onClick={() => setDuration(v)}
                      className={`text-[11px] font-black tracking-widest cursor-pointer transition-all ${duration === v ? 'text-brand scale-110' : 'text-slate-300 hover:text-slate-400'}`}
                    >
                      {v}m
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="premium-card p-8">
            <div className="flex justify-between items-center mb-8">
              <h3 className="font-bold text-slate-900 text-xl leading-none">Break Preferences</h3>
              <div className="w-10 h-10 rounded-2xl bg-emerald-50 flex items-center justify-center text-emerald-500">
                <Coffee size={20} />
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-4 block underline decoration-brand/20 decoration-2 underline-offset-4">Automatic Padding Type</label>
                <div className="grid grid-cols-2 gap-4 p-1.5 bg-slate-50 rounded-[24px]">
                  <button
                    onClick={() => setPaddingType('pre')}
                    className={`relative font-bold py-4 rounded-[18px] transition-all ${paddingType === 'pre' ? 'bg-white text-brand shadow-lg shadow-black/5' : 'text-slate-400 hover:text-slate-600'}`}
                  >
                    {paddingType === 'pre' && <motion.div layoutId="padding-bg" className="absolute inset-0 bg-white rounded-[18px] -z-10" />}
                    Pre-meeting
                  </button>
                  <button
                    onClick={() => setPaddingType('post')}
                    className={`relative font-bold py-4 rounded-[18px] transition-all ${paddingType === 'post' ? 'bg-white text-brand shadow-lg shadow-black/5' : 'text-slate-400 hover:text-slate-600'}`}
                  >
                    {paddingType === 'post' && <motion.div layoutId="padding-bg" className="absolute inset-0 bg-white rounded-[18px] -z-10" />}
                    Post-meeting
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="premium-card p-8">
            <div className="flex justify-between items-center mb-8">
              <h3 className="font-bold text-slate-900 text-xl leading-none">No-meeting time ranges</h3>
              <div className="w-10 h-10 rounded-2xl bg-brand/10 flex items-center justify-center text-brand">
                <Clock size={20} />
              </div>
            </div>

            <div className="space-y-4">
              {ranges.map((item, i) => (
                <div key={i} className="bg-slate-50/50 border-2 border-slate-50 p-5 rounded-[24px] flex items-center gap-5 hover:border-brand/10 transition-colors group relative">
                  <div className="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-xl">{item.icon}</div>
                  <div className="flex-1">
                    <h4 className="font-bold text-slate-900 text-base">{item.label}</h4>
                    <p className="text-[11px] font-black text-slate-400 mt-1 uppercase tracking-widest">{item.time}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => deleteRange(i)}
                      className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all"
                    >
                      <Trash2 size={18} />
                    </button>
                    <Toggle on={item.on} toggle={() => toggleRange(i)} />
                  </div>
                </div>
              ))}
            </div>

            <button 
              onClick={() => setIsModalOpen(true)}
              className="w-full mt-8 py-5 flex items-center justify-center gap-3 text-brand font-bold text-[11px] uppercase tracking-[0.2em] border-2 border-dashed border-brand/20 rounded-[28px] hover:bg-brand/5 hover:border-brand/40 transition-all"
            >
              <Plus size={18} /> Add new range
            </button>
          </div>

          <div className="bg-brand/5 border-2 border-dashed border-brand/10 p-8 rounded-[40px] flex items-center gap-6">
            <div className="w-16 h-24 bg-brand rounded-[28px] flex flex-col items-center justify-center text-white shadow-2xl shadow-brand/30">
              <motion.div
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="text-[10px] font-black uppercase mb-2 tracking-widest"
              >AI</motion.div>
              <Zap size={24} fill="currentColor" />
            </div>
            <div className="flex-1">
              <h4 className="font-bold text-slate-900 text-lg">AI Smart Scheduling</h4>
              <p className="text-[13px] font-medium text-slate-500 mt-2 leading-relaxed">Let AI adjust settings based on your fatigue levels.</p>
            </div>
            <Toggle on={aiScheduling} toggle={() => setAiScheduling(!aiScheduling)} />
          </div>
        </div>
      </div>
    </div>
  )
}

// --- MAIN APP COMPONENT ---
function App() {
  const [activeTab, setActiveTab] = useState('calendar')

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
            { id: 'calendar', label: 'My Schedule', icon: Calendar },
            { id: 'history', label: 'History Logs', icon: History },
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
          <div className="p-4 bg-white border border-slate-100 shadow-sm rounded-[24px] flex items-center gap-3 cursor-pointer hover:shadow-md transition-shadow">
            <div className="w-10 h-10 rounded-2xl bg-slate-100 overflow-hidden shrink-0 border-2 border-white">
              <img src={`https://api.dicebear.com/7.x/avataaars/svg?seed=Felix`} alt="Profile" />
            </div>
            <div className="hidden lg:block flex-1 min-w-0">
              <h4 className="font-bold text-slate-900 text-sm truncate">Alex Rivera</h4>
              <p className="text-[10px] font-bold text-slate-400 truncate uppercase mt-0.5">Product Manager</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 ml-[100px] lg:ml-[280px] p-10 lg:p-16 lg:px-20 max-w-[1500px] mx-auto min-h-screen pb-32">
        <header className="flex justify-between items-center mb-20 px-2">
          <div>
            <motion.span
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-[11px] font-black text-brand uppercase tracking-[0.3em] mb-2 block"
            >Good Morning, Alex</motion.span>
            <motion.h2
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-5xl font-black text-slate-900 tracking-tight"
            >Let's optimize your <span className="text-brand">{new Date().toLocaleDateString('default', { weekday: 'long' })}.</span></motion.h2>
          </div>
          <div className="flex gap-4">
            <button className="premium-card p-4 text-slate-400 hover:text-brand transition-colors shadow-none border-none"><Search size={24} /></button>
            <button className="premium-card p-4 text-slate-400 hover:text-brand transition-colors shadow-none border-none"><Bell size={24} /></button>
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
            {activeTab === 'calendar' && <DashboardPage />}
            {activeTab === 'settings' && <PreferencesPage />}
            {activeTab === 'chat' && <ChatPage />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}

export default App
