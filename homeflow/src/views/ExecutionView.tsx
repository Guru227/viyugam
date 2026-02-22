import { useState } from 'react';
import { startOfWeek, addDays, format, isToday, subWeeks, addWeeks } from 'date-fns';
import { 
  Calendar, 
  ChevronLeft, 
  ChevronRight, 
  Layout, 
  BarChart2, 
  Plus, 
  GripVertical,
  Clock,
  Flag,
  Briefcase,
  BookOpen,
  Target,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  DollarSign,
  Flame
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer
} from 'recharts';
import type { Task } from '../types';

// --- MOCK DATA ---

const BACKLOG_TASKS: Task[] = [
    { id: 'b1', milestoneId: 'm9', title: 'Research Competitors', status: 'todo', project: 'Launch Side Hustle', duration: 120, deadline: new Date('2023-12-01') },
    { id: 'b2', milestoneId: 'm9', title: 'Draft Marketing Copy', status: 'todo', project: 'Launch Side Hustle', duration: 60, deadline: new Date('2023-12-05') },
    { id: 'b3', milestoneId: 'm9', title: 'Update Resume', status: 'todo', project: 'Career Growth', duration: 45 },
    { id: 'b4', milestoneId: 'm9', title: 'Clean Garage', status: 'todo', project: 'Home Maint.', duration: 180, deadline: new Date('2023-11-30') },
];

const MOCK_WEEKLY_TASKS: Record<string, Task[]> = {
  'Mon': [
    { id: 't3', milestoneId: 'm2', title: 'Interval training', status: 'done', startTime: '07:00', duration: 60, project: 'Marathon' },
    { id: 't5', milestoneId: 'm5', title: 'Setup React project', status: 'done', startTime: '09:00', duration: 120, project: 'Side Hustle' },
  ],
  'Tue': [
    { id: 't6', milestoneId: 'm5', title: 'Build landing page', status: 'doing', startTime: '10:00', duration: 180, project: 'Side Hustle' },
  ],
  'Wed': [
    { id: 't2', milestoneId: 'm1', title: 'Run 5k', status: 'todo', startTime: '07:00', duration: 45, project: 'Marathon' },
    { id: 't8', milestoneId: 'm1', title: 'Team Sync', status: 'todo', startTime: '14:00', duration: 60, project: 'Career' },
  ],
  'Thu': [],
  'Fri': [
    { id: 't7', milestoneId: 'm5', title: 'Integrate payments', status: 'todo', startTime: '13:00', duration: 120, project: 'Side Hustle' },
  ],
  'Sat': [
    { id: 't4', milestoneId: 'm2', title: 'Long run (15k)', status: 'todo', startTime: '08:00', duration: 150, project: 'Marathon' },
  ],
  'Sun': []
};

const MOOD_ENERGY_DATA = [
  { day: 'Mon', energy: 8, mood: 7 },
  { day: 'Tue', energy: 6, mood: 6 },
  { day: 'Wed', energy: 9, mood: 8 },
  { day: 'Thu', energy: 7, mood: 5 },
  { day: 'Fri', energy: 5, mood: 6 },
  { day: 'Sat', energy: 9, mood: 9 },
  { day: 'Sun', energy: 8, mood: 9 },
];

const WEEKLY_METRICS = {
    avgBalance: 78,
    avgCircadian: 82,
    avgCognitive: 65,
    avgTotalScore: 75,
    totalTasks: 24,
    totalBudget: 450,
    priorityBreakup: { high: 8, medium: 12, low: 4 },
    journalStreak: 12
};

const JOURNAL_ENTRIES = [
    { id: 'j1', date: 'Mon, Nov 27', title: 'Strong Start', snippet: 'Felt really energetic this morning. The interval training was tough but rewarding.' },
    { id: 'j2', date: 'Wed, Nov 29', title: 'Mid-week Slump', snippet: 'Struggled to focus in the afternoon. Need to adjust my lunch timing.' },
    { id: 'j3', date: 'Fri, Dec 01', title: 'Productive Flow', snippet: 'Got into a deep flow state with the coding task. Payments integration is tricky but fun.' },
];

// --- HELPERS ---

const timeToFloat = (time: string) => {
    const [h, m] = time.split(':').map(Number);
    return h + m / 60;
};

const HOURS = Array.from({ length: 17 }, (_, i) => i + 6); // 6 AM to 10 PM

// --- COMPONENTS ---

export function ExecutionView() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [activeTab, setActiveTab] = useState<'planner' | 'velocity'>('planner');
  
  const startDate = startOfWeek(currentDate, { weekStartsOn: 1 }); // Monday start
  const weekDays = Array.from({ length: 7 }).map((_, i) => addDays(startDate, i));

  const handlePrevWeek = () => setCurrentDate(subWeeks(currentDate, 1));
  const handleNextWeek = () => setCurrentDate(addWeeks(currentDate, 1));

  return (
    <div id="execution" className="w-full h-full p-8 snap-start overflow-y-auto bg-slate-50">
      <div className="w-full h-full flex flex-col">
        {/* Header & Controls */}
        <div className="mb-6 flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-bold text-slate-800 mb-2 font-sans">Execution Focus</h1>
            <p className="text-xl text-slate-500">The Scheduler — Sprint Planning & Velocity</p>
          </div>
          
          <div className="flex flex-col items-end gap-3">
              {/* Week Switcher (Global for View) */}
              <div className="flex items-center gap-4 bg-white p-1.5 rounded-xl border border-slate-200 shadow-sm">
                    <button onClick={handlePrevWeek} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-slate-600 transition-colors">
                        <ChevronLeft size={20} />
                    </button>
                    <div className="flex items-center gap-2 font-bold text-slate-700 min-w-[180px] justify-center">
                        <Calendar size={18} className="text-orange-500" />
                        <span>{format(startDate, 'MMM d')} - {format(addDays(startDate, 6), 'MMM d, yyyy')}</span>
                    </div>
                    <button onClick={handleNextWeek} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-slate-600 transition-colors">
                        <ChevronRight size={20} />
                    </button>
              </div>

              {/* Tab Switcher */}
              <div className="flex bg-white rounded-lg p-1 border border-slate-200 shadow-sm">
                <button 
                    onClick={() => setActiveTab('planner')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'planner' ? 'bg-orange-100 text-orange-700 shadow-sm' : 'text-slate-500 hover:bg-slate-50'}`}
                >
                    <Layout size={16} />
                    Sprint Planner
                </button>
                <button 
                    onClick={() => setActiveTab('velocity')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'velocity' ? 'bg-orange-100 text-orange-700 shadow-sm' : 'text-slate-500 hover:bg-slate-50'}`}
                >
                    <BarChart2 size={16} />
                    Velocity Check
                </button>
              </div>
          </div>
        </div>

        {activeTab === 'planner' ? (
            <div className="flex-1 min-h-0 flex gap-6 overflow-hidden">
                {/* Left Pane: Backlog */}
                <div className="w-80 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col flex-shrink-0">
                    <div className="p-4 border-b border-slate-100 bg-slate-50/50 rounded-t-xl">
                        <h3 className="font-bold text-slate-700 uppercase text-xs tracking-wider">Backlog</h3>
                        <p className="text-xs text-slate-400 mt-1">Drag items to the calendar</p>
                    </div>
                    <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                        {BACKLOG_TASKS.map(task => (
                            <div key={task.id} className="p-3 bg-white border border-slate-200 rounded-lg shadow-sm hover:shadow-md hover:border-orange-300 transition-all cursor-move group">
                                <div className="flex items-center gap-2 mb-2">
                                    <GripVertical size={14} className="text-slate-300 group-hover:text-slate-400" />
                                    <span className="text-sm font-bold text-slate-700">{task.title}</span>
                                </div>
                                <div className="flex flex-wrap gap-2 pl-5">
                                    {task.project && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-600 border border-blue-100">
                                            <Briefcase size={10} /> {task.project}
                                        </span>
                                    )}
                                    {task.duration && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                                            <Clock size={10} /> {task.duration}m
                                        </span>
                                    )}
                                    {task.deadline && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-50 text-red-600 border border-red-100">
                                            <Flag size={10} /> {format(task.deadline, 'MMM d')}
                                        </span>
                                    )}
                                </div>
                            </div>
                        ))}
                        <button className="w-full py-2 flex items-center justify-center gap-2 text-xs font-bold text-slate-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg border border-dashed border-slate-200 transition-colors">
                            <Plus size={14} />
                            Add Item
                        </button>
                    </div>
                </div>

                {/* Right Pane: Calendar (Week Timeline) */}
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col overflow-hidden">
                    {/* Calendar Grid */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar relative">
                        <div className="min-w-[800px] relative">
                            {/* Header Row (Days) */}
                            <div className="flex sticky top-0 z-20 bg-white border-b border-slate-100 shadow-sm">
                                <div className="w-16 flex-shrink-0 border-r border-slate-100 bg-slate-50/50"></div> {/* Time Axis Header */}
                                {weekDays.map((day, i) => (
                                    <div key={i} className={`flex-1 p-2 text-center border-r border-slate-100 last:border-r-0 ${isToday(day) ? 'bg-orange-50/30' : ''}`}>
                                        <div className="text-[10px] font-bold text-slate-400 uppercase">{format(day, 'EEE')}</div>
                                        <div className={`text-sm font-bold ${isToday(day) ? 'text-orange-600' : 'text-slate-700'}`}>
                                            {format(day, 'd')}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Time Grid */}
                            <div className="flex relative">
                                {/* Time Axis */}
                                <div className="w-16 flex-shrink-0 border-r border-slate-100 bg-slate-50/30">
                                    {HOURS.map(hour => (
                                        <div key={hour} className="h-20 border-b border-slate-100 text-[10px] text-slate-400 font-medium text-right pr-2 pt-1 relative">
                                            <span className="relative -top-2">{hour > 12 ? `${hour - 12} PM` : hour === 12 ? '12 PM' : `${hour} AM`}</span>
                                        </div>
                                    ))}
                                </div>

                                {/* Day Columns */}
                                {weekDays.map((day, i) => {
                                    const dayName = format(day, 'EEE');
                                    const tasks = MOCK_WEEKLY_TASKS[dayName] || [];
                                    
                                    return (
                                        <div key={i} className={`flex-1 border-r border-slate-100 last:border-r-0 relative ${isToday(day) ? 'bg-orange-50/10' : ''}`}>
                                            {/* Grid Lines */}
                                            {HOURS.map(hour => (
                                                <div key={hour} className="h-20 border-b border-slate-50"></div>
                                            ))}

                                            {/* Tasks */}
                                            {tasks.map((task, index) => {
                                                if (!task.startTime || !task.duration) return null;
                                                const start = timeToFloat(task.startTime);
                                                const top = (start - 6) * 80; // 80px per hour, starting at 6 AM
                                                const height = (task.duration / 60) * 80;

                                                return (
                                                    <div 
                                                        key={index}
                                                        className="absolute left-1 right-1 rounded-lg border border-orange-200 bg-orange-50 p-2 shadow-sm hover:shadow-md hover:z-10 transition-all cursor-pointer overflow-hidden"
                                                        style={{ top: `${top}px`, height: `${height}px` }}
                                                    >
                                                        <div className="text-[10px] font-bold text-orange-800 leading-tight mb-0.5">{task.title}</div>
                                                        <div className="text-[9px] text-orange-600 flex items-center gap-1">
                                                            <Clock size={8} /> {task.startTime} ({task.duration}m)
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        ) : (
            <div className="flex-1 flex flex-col gap-6 overflow-y-auto custom-scrollbar pr-2">
                {/* Top Row: Metrics Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Avg Total Score */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
                        <div className="p-3 bg-indigo-100 text-indigo-600 rounded-xl">
                            <Target size={24} />
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-slate-800">{WEEKLY_METRICS.avgTotalScore}%</div>
                            <div className="text-xs font-bold text-slate-400 uppercase">Avg Total Score</div>
                        </div>
                    </div>

                    {/* Journal Streak */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
                        <div className="p-3 bg-orange-100 text-orange-600 rounded-xl">
                            <Flame size={24} />
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-slate-800">{WEEKLY_METRICS.journalStreak} Days</div>
                            <div className="text-xs font-bold text-slate-400 uppercase">Journal Streak</div>
                        </div>
                    </div>

                    {/* Total Tasks */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
                        <div className="p-3 bg-emerald-100 text-emerald-600 rounded-xl">
                            <CheckCircle2 size={24} />
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-slate-800">{WEEKLY_METRICS.totalTasks}</div>
                            <div className="text-xs font-bold text-slate-400 uppercase">Tasks Completed</div>
                        </div>
                    </div>

                    {/* Budget */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
                        <div className="p-3 bg-blue-100 text-blue-600 rounded-xl">
                            <DollarSign size={24} />
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-slate-800">${WEEKLY_METRICS.totalBudget}</div>
                            <div className="text-xs font-bold text-slate-400 uppercase">Total Budget</div>
                        </div>
                    </div>
                </div>

                {/* Second Row: Detailed Stats & Priority */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Detailed Scores */}
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <TrendingUp size={18} className="text-slate-400" /> Performance Metrics
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="text-slate-600 font-medium">Balance Score</span>
                                    <span className="text-slate-800 font-bold">{WEEKLY_METRICS.avgBalance}%</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${WEEKLY_METRICS.avgBalance}%` }}></div>
                                </div>
                            </div>
                            <div>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="text-slate-600 font-medium">Circadian Score</span>
                                    <span className="text-slate-800 font-bold">{WEEKLY_METRICS.avgCircadian}%</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${WEEKLY_METRICS.avgCircadian}%` }}></div>
                                </div>
                            </div>
                            <div>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="text-slate-600 font-medium">Cognitive Load</span>
                                    <span className="text-slate-800 font-bold">{WEEKLY_METRICS.avgCognitive}%</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div className="h-full bg-rose-500 rounded-full" style={{ width: `${WEEKLY_METRICS.avgCognitive}%` }}></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Priority Breakup */}
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <AlertCircle size={18} className="text-slate-400" /> Task Priority
                        </h3>
                        <div className="flex items-end justify-center gap-4 h-32">
                            <div className="w-16 flex flex-col items-center gap-2 group">
                                <div className="text-sm font-bold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity">{WEEKLY_METRICS.priorityBreakup.high}</div>
                                <div className="w-full bg-red-100 rounded-t-lg relative overflow-hidden" style={{ height: '80%' }}>
                                    <div className="absolute bottom-0 w-full bg-red-500" style={{ height: '100%' }}></div>
                                </div>
                                <span className="text-xs font-bold text-slate-500 uppercase">High</span>
                            </div>
                            <div className="w-16 flex flex-col items-center gap-2 group">
                                <div className="text-sm font-bold text-amber-600 opacity-0 group-hover:opacity-100 transition-opacity">{WEEKLY_METRICS.priorityBreakup.medium}</div>
                                <div className="w-full bg-amber-100 rounded-t-lg relative overflow-hidden" style={{ height: '60%' }}>
                                    <div className="absolute bottom-0 w-full bg-amber-500" style={{ height: '100%' }}></div>
                                </div>
                                <span className="text-xs font-bold text-slate-500 uppercase">Med</span>
                            </div>
                            <div className="w-16 flex flex-col items-center gap-2 group">
                                <div className="text-sm font-bold text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity">{WEEKLY_METRICS.priorityBreakup.low}</div>
                                <div className="w-full bg-blue-100 rounded-t-lg relative overflow-hidden" style={{ height: '40%' }}>
                                    <div className="absolute bottom-0 w-full bg-blue-500" style={{ height: '100%' }}></div>
                                </div>
                                <span className="text-xs font-bold text-slate-500 uppercase">Low</span>
                            </div>
                        </div>
                    </div>

                    {/* Mood Graph (Compact) */}
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex flex-col">
                        <h3 className="text-lg font-bold text-slate-800 mb-2">Mood & Energy</h3>
                        <div className="flex-1 min-h-0">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={MOOD_ENERGY_DATA}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                    <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
                                    <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
                                    <Line type="monotone" dataKey="energy" stroke="#fbbf24" strokeWidth={2} dot={false} />
                                    <Line type="monotone" dataKey="mood" stroke="#6366f1" strokeWidth={2} dot={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                {/* Bottom Row: Reflection Journal */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex-1">
                    <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <BookOpen size={18} className="text-slate-400" /> Weekly Reflections
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {JOURNAL_ENTRIES.map(entry => (
                            <div key={entry.id} className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-indigo-200 transition-colors cursor-pointer">
                                <div className="text-xs font-bold text-indigo-500 uppercase mb-1">{entry.date}</div>
                                <h4 className="font-bold text-slate-800 mb-2">{entry.title}</h4>
                                <p className="text-sm text-slate-600 line-clamp-3 italic">"{entry.snippet}"</p>
                            </div>
                        ))}
                        <div className="p-4 border-2 border-dashed border-slate-200 rounded-xl flex flex-col items-center justify-center text-slate-400 hover:text-indigo-500 hover:border-indigo-200 hover:bg-indigo-50 transition-all cursor-pointer group">
                            <Plus size={24} className="mb-2 group-hover:scale-110 transition-transform" />
                            <span className="text-sm font-bold">Log Reflection</span>
                        </div>
                    </div>
                </div>
            </div>
        )}
      </div>
    </div>
  );
}
