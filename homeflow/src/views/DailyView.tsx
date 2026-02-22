import { useState } from 'react';
import { 
  Clock, 
  DollarSign, 
  Briefcase, 
  Star, 
  CheckCircle2, 
  Play, 
  X, 
  Plus, 
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { format, addDays, subDays, isSameDay } from 'date-fns';
import type { DailyTask } from '../types';

// --- CONSTANTS & HELPERS ---

const DAY_PERIODS = [
    { startHour: 5, endHour: 10, name: 'Early Morning', bgColor: 'bg-yellow-100', emoji: '☀️', text: 'text-yellow-800' },
    { startHour: 10, endHour: 17, name: 'Afternoon', bgColor: 'bg-orange-100', emoji: '🌞', text: 'text-orange-800' },
    { startHour: 17, endHour: 22, name: 'Evening', bgColor: 'bg-rose-100', emoji: '🌇', text: 'text-rose-800' },
    { startHour: 22, endHour: 29, name: 'Night', bgColor: 'bg-indigo-100', emoji: '🌙', text: 'text-indigo-800' },
];

const getTimePeriod = (hourFloat: number) => {
    const hour = hourFloat % 24; 
    const period = DAY_PERIODS.find(p => {
        if (p.name === 'Night') return hour >= p.startHour || hour < (p.endHour % 24);
        return hour >= p.startHour && hour < p.endHour;
    });
    return period || DAY_PERIODS[0];
};

const parseTimeSlot = (timeSlot: string | null): [number, number] => {
    if (!timeSlot) return [0, 0];
    const [startStr, endStr] = (timeSlot.split(' - ').map(s => s.trim()) || ['', '']).slice(0, 2);
    
    const parseTime = (time: string) => {
        if (!time) return 0;
        const match = time.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (!match) {
             const [h, m] = time.split(':').map(s => parseInt(s) || 0);
             return (h % 24) + (m / 60);
        }
        let [_, hourStr, minuteStr, ampm] = match;
        let h = parseInt(hourStr);
        const m = parseInt(minuteStr);
        ampm = ampm ? ampm.toUpperCase() : '';
        if (ampm === 'PM' && h !== 12) h += 12;
        if (ampm === 'AM' && h === 12) h = 0;
        return h + m / 60;
    };
    
    const start = parseTime(startStr);
    const end = parseTime(endStr);
    if (end < start) return [start, end + 24];
    return [start, end];
};

const calculateScores = (tasks: DailyTask[]) => {
    if (tasks.length === 0) return { balance: 50, circadian: 50, cognitive: 50, totalScheduledMinutes: 0, completedTasks: 0 };
    let highPriorityCount = 0;
    let scheduledMinutes = 0;
    let optimalTimeScheduledMinutes = 0; 
    let completedTasks = 0;

    tasks.forEach(task => {
        if (task.taskPriority === 'High') highPriorityCount++;
        if (task.status === 'completed') completedTasks++;
        const [start, end] = parseTimeSlot(task.timeSlot);
        const durationMinutes = (end - start) * 60;
        scheduledMinutes += durationMinutes;
        const optimalStart = 8.0;
        const optimalEnd = 13.0;
        const overlapStart = Math.max(start, optimalStart);
        const overlapEnd = Math.min(end, optimalEnd);
        if (overlapEnd > overlapStart) optimalTimeScheduledMinutes += (overlapEnd - overlapStart) * 60;
    });

    const totalMinutesInDay = 24 * 60;
    const scheduledPercentage = (scheduledMinutes / totalMinutesInDay) * 100;
    const balanceScore = Math.max(0, Math.min(100, 100 - scheduledPercentage * 1.5));
    const circadianScore = Math.min(100, (optimalTimeScheduledMinutes / 300) * 100);
    const maxHighTasks = 5;
    const cognitiveScore = Math.max(0, 100 - (highPriorityCount / maxHighTasks) * 100);

    return { balance: Math.round(balanceScore), circadian: Math.round(circadianScore), cognitive: Math.round(cognitiveScore), totalScheduledMinutes: scheduledMinutes, completedTasks: completedTasks };
};

// --- SUB-COMPONENTS ---

const DateSwitcher = ({ currentDate, onDateChange }: { currentDate: Date, onDateChange: (date: Date) => void }) => {
    return (
        <div className="flex items-center gap-4 bg-white p-1.5 rounded-xl border border-slate-200 shadow-sm">
            <button onClick={() => onDateChange(subDays(currentDate, 1))} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors">
                <ChevronLeft size={18} />
            </button>
            <div className="flex flex-col items-center min-w-[120px]">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    {isSameDay(currentDate, new Date()) ? 'Today' : format(currentDate, 'EEEE')}
                </span>
                <span className="text-sm font-bold text-slate-800">
                    {format(currentDate, 'MMM d, yyyy')}
                </span>
            </div>
            <button onClick={() => onDateChange(addDays(currentDate, 1))} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors">
                <ChevronRight size={18} />
            </button>
        </div>
    );
};

const TaskCard = ({ task, onDelete, onUpdateStatus }: { task: DailyTask; onDelete: (id: string) => void; onUpdateStatus: (id: string, status: DailyTask['status']) => void }) => {
    const timeSlot = task.timeSlot;
    const [startHourFloat] = parseTimeSlot(timeSlot || '7:00 AM - 7:00 AM');
    const period = getTimePeriod(startHourFloat);

    let statusClasses = 'border-l-4 border-gray-300';
    let statusBg = period.bgColor;
    if (task.status === 'started') {
        statusClasses = 'border-l-4 border-yellow-500 shadow-md';
        statusBg = 'bg-yellow-50';
    } else if (task.status === 'completed') {
        statusClasses = 'border-l-4 border-emerald-500 opacity-70';
        statusBg = 'bg-emerald-50';
    }
    
    const getPriorityColor = (priority: string) => {
        if (priority === 'High') return 'bg-red-500 text-white';
        if (priority === 'Medium') return 'bg-amber-400 text-gray-800';
        return 'bg-blue-300 text-gray-800';
    };

    return (
        <div className={`p-3 shadow-lg rounded-xl transition-shadow hover:shadow-xl ${statusClasses} ${statusBg}`}>
            <div className="flex justify-between items-start">
                <h3 className={`text-lg font-bold leading-tight ${task.status === 'completed' ? 'line-through text-gray-500' : 'text-gray-800'}`}>{task.name}</h3>
                <button onClick={() => onDelete(task.id)} className="p-1 rounded-full text-gray-400 hover:text-red-500 transition-colors flex-shrink-0"><X className="w-4 h-4" /></button>
            </div>
            <p className={`text-sm mt-1 ${task.status === 'completed' ? 'line-through text-gray-400' : 'text-gray-600'}`}>{task.description}</p>
            <div className="mt-2 flex flex-wrap items-center justify-between text-xs space-x-2 border-t border-gray-100 pt-2">
                <div className="flex items-center space-x-1"><Briefcase className="w-3 h-3 text-gray-500" /><span className="font-medium text-gray-700">{task.project || 'General'}</span></div>
                <div className="flex items-center space-x-1"><DollarSign className="w-3 h-3 text-emerald-600" /><span className="font-semibold text-emerald-700">${task.cashBudget.toFixed(2)}</span></div>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${getPriorityColor(task.taskPriority)}`}>{task.taskPriority}</span>
                <div className="flex space-x-1 mt-2 sm:mt-0">
                    {task.status !== 'completed' && (
                        <button onClick={() => onUpdateStatus(task.id, task.status === 'started' ? 'pending' : 'started')} className={`p-1 rounded-full transition-colors ${task.status === 'started' ? 'bg-yellow-400 text-white' : 'bg-gray-200 text-gray-600 hover:bg-yellow-200'}`}><Play className="w-4 h-4" /></button>
                    )}
                    <button onClick={() => onUpdateStatus(task.id, 'completed')} className={`p-1 rounded-full transition-colors ${task.status === 'completed' ? 'bg-emerald-500 text-white' : 'bg-gray-200 text-gray-600 hover:bg-emerald-200'}`}><CheckCircle2 className="w-4 h-4" /></button>
                </div>
            </div>
        </div>
    );
};

const DailyCalendarView = ({ tasks, deleteTask, updateTaskStatus }: { tasks: DailyTask[]; deleteTask: (id: string) => void; updateTaskStatus: (id: string, status: DailyTask['status']) => void }) => {
    const formatDuration = (minutes: number) => {
        const h = Math.floor(minutes / 60);
        const m = Math.round(minutes % 60);
        if (h > 0) return `${h}h ${m > 0 ? `${m}m` : ''}`;
        return `${m}m`;
    };

    const sortedTasks = [...tasks]
        .filter(t => t.timeSlot)
        .sort((a, b) => parseTimeSlot(a.timeSlot)[0] - parseTimeSlot(b.timeSlot)[0]);

    const timelineItems: any[] = [];
    let currentTimeSlotEndFloat = parseTimeSlot('00:00 AM - 00:00 AM')[0];

    const formatHourFloat = (hourFloat: number) => {
         const h = Math.floor(hourFloat % 24);
         const m = Math.round((hourFloat % 1) * 60);
         const [hour, minute] = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`.split(':').map(Number);
         let ampm = 'AM';
         let displayHour = hour;
         if (hour === 0 || hour === 24) { displayHour = 12; } 
         else if (hour === 12) { ampm = 'PM'; } 
         else if (hour > 12) { displayHour = hour - 12; ampm = 'PM'; }
         return `${displayHour.toString().padStart(2, '0').slice(-2)}:${minute.toString().padStart(2, '0')} ${ampm}`;
    }

    sortedTasks.forEach((task) => {
        const [startFloat, endFloat] = parseTimeSlot(task.timeSlot);
        let gapDurationFloat = 0;
        
        if (startFloat > currentTimeSlotEndFloat + 0.001) {
             gapDurationFloat = startFloat - currentTimeSlotEndFloat;
        } else if (startFloat < currentTimeSlotEndFloat - 0.001) {
             if (currentTimeSlotEndFloat >= 24) {
                 const adjustedEnd = currentTimeSlotEndFloat % 24;
                 if (startFloat > adjustedEnd + 0.001) {
                     gapDurationFloat = startFloat - adjustedEnd;
                 }
             }
        }
        
        if (gapDurationFloat * 60 > 15) { 
            timelineItems.push({
                type: 'gap',
                start: formatHourFloat(currentTimeSlotEndFloat),
                end: formatHourFloat(startFloat),
                duration: gapDurationFloat * 60,
                startFloat: currentTimeSlotEndFloat,
            });
        }
        
        timelineItems.push({ type: 'task', task: task, time: task.timeSlot, startFloat: startFloat });
        currentTimeSlotEndFloat = endFloat;
    });

    return (
        <div className="space-y-4 h-full overflow-y-auto custom-scrollbar bg-white p-4 rounded-xl shadow-sm border border-slate-100">
            {timelineItems.length === 0 ? (
                <div className="p-10 bg-gray-50 rounded-xl text-center text-gray-500 border-2 border-dashed border-gray-300">
                    <Clock className="w-12 h-12 mx-auto mb-3 text-gray-400"/>
                    <p className="text-lg font-semibold">Daily Schedule is Empty</p>
                    <p className="text-sm mt-1">Add tasks with a Time Slot (e.g., 09:00 AM - 10:00 AM) to see your calendar.</p>
                </div>
            ) : (
                timelineItems.map((item, index) => {
                    if (item.type === 'task') {
                         const period = getTimePeriod(item.startFloat);
                         let showEmoji = true;
                         if (index > 0) {
                             const prevItem = timelineItems[index - 1];
                             let prevEndFloat = prevItem.type === 'task' ? parseTimeSlot(prevItem.task.timeSlot)[1] : item.startFloat;
                             const prevPeriod = prevItem.type === 'task' ? getTimePeriod(prevEndFloat) : getTimePeriod(prevItem.startFloat);
                             showEmoji = period.name !== prevPeriod.name;
                         }

                        return (
                            <div key={item.task.id || index} className="flex space-x-4 items-start">
                                <div className="flex-shrink-0 w-24 text-right pt-2">
                                    <span className="text-sm font-bold text-gray-700">{item.time.split(' - ')[0]}</span>
                                    {showEmoji && <span className="ml-1 text-lg" role="img" aria-label={period.name}>{period.emoji}</span>}
                                </div>
                                <div className={`flex-grow border-l-2 border-pink-400 pl-4 relative ${period.bgColor} rounded-xl p-0.5`}>
                                    <div className="absolute left-[-6px] top-3 w-3 h-3 bg-pink-500 rounded-full border-2 border-white"></div>
                                    <TaskCard task={item.task} onDelete={deleteTask} onUpdateStatus={updateTaskStatus} />
                                </div>
                            </div>
                        );
                    } else if (item.type === 'gap') {
                        const period = getTimePeriod(item.startFloat);
                        return (
                             <div key={index} className="flex space-x-4 items-center mb-4">
                                <div className="flex-shrink-0 w-24 text-right"><span className="text-xs text-gray-400">{item.start}</span></div>
                                <div className={`flex-grow border-l-2 border-gray-300 border-dashed pl-4 py-2 relative ${period.bgColor} rounded-xl`}>
                                    <div className="absolute left-[-4px] top-1/2 -translate-y-1/2 w-2 h-2 bg-gray-400 rounded-full"></div>
                                    <p className="text-xs font-semibold text-gray-500 p-2 rounded-lg text-center">Free Time Slot ({formatDuration(item.duration)})</p>
                                </div>
                            </div>
                        );
                    }
                    return null;
                })
            )}
        </div>
    );
};

const TimeFlowGraph = ({ tasks }: { tasks: DailyTask[] }) => {
    const occupancy = Array(24).fill(0);
    tasks.forEach(task => {
        const [startHourFloat, endHourFloat] = parseTimeSlot(task.timeSlot);
        for (let h = 0; h < 24; h++) {
            if ((h + 1 > startHourFloat + 0.001) && (h < endHourFloat - 0.001)) occupancy[h] = 1;
        }
    });
    const maxGraphHeight = 50;
    const widthUnit = 40;
    const totalWidth = 24 * widthUnit;

    return (
        <div className="w-full overflow-x-auto custom-scrollbar bg-gray-50 rounded-lg shadow-inner p-1">
             <div className="w-full h-24" style={{ minWidth: totalWidth }}>
                <svg viewBox={`0 0 ${totalWidth} ${maxGraphHeight + 15}`} style={{ width: totalWidth, height: '100%' }}>
                    <line x1="0" y1={maxGraphHeight} x2={totalWidth} y2={maxGraphHeight} stroke="#d1d5db" strokeWidth="0.5" />
                    {occupancy.map((isBusy, index) => {
                        const x = index * widthUnit;
                        const y = isBusy ? 0 : maxGraphHeight;
                        const fill = isBusy ? '#F472B6' : '#E5E7EB';
                        return <rect key={index} x={x} y={y} width={widthUnit} height={maxGraphHeight - y} fill={fill} className="transition-all duration-300" />;
                    })}
                    {[...Array(25).keys()].map(hour => {
                        if (hour % 2 !== 0 && hour !== 24) return null;
                        const textX = hour * widthUnit;
                        const label = hour === 0 || hour === 24 ? '12a' : (hour === 12 ? '12p' : (hour > 12 ? `${hour - 12}p` : `${hour}a`));
                        return <text key={hour} x={textX} y={maxGraphHeight + 10} fontSize="6" fill="#6b7280" textAnchor={hour === 0 ? "start" : (hour === 24 ? "end" : "middle")}>{label}</text>;
                    })}
                </svg>
            </div>
            <p className="text-center text-xs text-gray-500 mt-1">TimeFlow Occupancy (24h)</p>
        </div>
    );
};

const DailySummaryView = ({ tasks, scores, currentDate }: { tasks: DailyTask[]; scores: any, currentDate: Date }) => {
    const formattedDate = format(currentDate, 'EEEE, MMMM d');
    const tasksToDisplay = tasks.filter(t => t.timeSlot);
    const highPriorityCount = tasksToDisplay.filter(t => t.taskPriority === 'High').length;
    const totalBudget = tasksToDisplay.reduce((sum, t) => sum + t.cashBudget, 0);

    const ScoreCard = ({ title, score, color, icon: Icon }: any) => (
        <div className={`p-4 rounded-xl shadow-sm bg-white border border-slate-100`}>
            <div className="flex items-center justify-between mb-2"><p className="text-xs font-bold text-gray-500 uppercase">{title}</p><Icon className={`w-4 h-4 ${color}`} /></div>
            <p className={`text-3xl font-extrabold ${color}`}>{score}<span className="text-sm text-gray-400">%</span></p>
        </div>
    );
    const formatDuration = (minutes: number) => {
        const h = Math.floor(minutes / 60);
        const m = Math.round(minutes % 60);
        if (h > 0) return `${h}h ${m > 0 ? `${m}m` : ''}`;
        return `${m}m`;
    };

    return (
        <div className="space-y-6 h-full overflow-y-auto custom-scrollbar pr-2">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <h3 className="text-xl font-bold text-gray-800 mb-1">Daily Focus Summary</h3>
                <p className="text-sm text-gray-500 mb-4">{formattedDate}</p>
                
                <div className="grid grid-cols-1 gap-3 mb-6">
                    <ScoreCard title="Balance Score" score={scores.balance} color="text-emerald-600" icon={Star} />
                    <ScoreCard title="Circadian Score" score={scores.circadian} color="text-indigo-600" icon={Clock} />
                    <ScoreCard title="Cognitive Load" score={scores.cognitive} color="text-red-600" icon={Briefcase} />
                </div>

                <div className="grid grid-cols-2 gap-3 text-center border-t border-slate-100 pt-4 mb-6">
                     <div className="p-2 rounded-lg bg-pink-50"><p className="text-xl font-extrabold text-pink-700">{tasksToDisplay.length}</p><p className="text-[10px] font-bold text-gray-500 uppercase">Tasks</p></div>
                    <div className="p-2 rounded-lg bg-red-50"><p className="text-xl font-extrabold text-red-700">{highPriorityCount}</p><p className="text-[10px] font-bold text-gray-500 uppercase">High Prio</p></div>
                    <div className="p-2 rounded-lg bg-emerald-50"><p className="text-lg font-extrabold text-emerald-700">${totalBudget.toFixed(0)}</p><p className="text-[10px] font-bold text-gray-500 uppercase">Budget</p></div>
                    <div className="p-2 rounded-lg bg-blue-50"><p className="text-xl font-extrabold text-blue-700">{scores.completedTasks}</p><p className="text-[10px] font-bold text-gray-500 uppercase">Done</p></div>
                </div>
                
                <TimeFlowGraph tasks={tasksToDisplay} />
                <p className="text-xs text-gray-400 mt-2 text-center">Total Scheduled: {formatDuration(scores.totalScheduledMinutes)}</p>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <h4 className="text-sm font-bold text-indigo-800 flex items-center mb-2"><Star className="w-4 h-4 mr-2 text-indigo-500" />Reflection Log</h4>
                <div className="h-32 p-3 bg-slate-50 rounded-lg border border-slate-100 overflow-y-auto custom-scrollbar text-sm text-gray-500 italic">
                    No reflections logged yet. Use the Flow Coach to capture your thoughts.
                </div>
            </div>
        </div>
    );
};

const TaskForm = ({ onAddTask, isVisible, currentDate }: { onAddTask: (task: DailyTask) => void; isVisible: boolean; currentDate: Date }) => {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [project, setProject] = useState(''); 
    const [timeSlot, setTimeSlot] = useState(''); 
    const [cashBudget, setCashBudget] = useState(0);
    const [taskPriority, setTaskPriority] = useState<'High' | 'Medium' | 'Low'>('Medium');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        setError(null);
        const newTask: DailyTask = {
            id: `task-${Date.now()}`,
            name, 
            description, 
            project, 
            planningHorizon: 'Daily Focus', 
            timeSlot: timeSlot || null, 
            cashBudget: Number(cashBudget) || 0, 
            taskPriority, 
            status: 'pending', 
            date: format(currentDate, 'yyyy-MM-dd'),
            createdAt: new Date().toISOString(),
        };
        onAddTask(newTask);
        setName(''); setDescription(''); setProject(''); setTimeSlot(''); setCashBudget(0); setTaskPriority('Medium');
        setIsSubmitting(false);
    };

    if (!isVisible) return null;

    return (
        <form onSubmit={handleSubmit} className="p-6 bg-white rounded-xl shadow-2xl space-y-5 max-w-xl mx-auto border-t-4 border-blue-500 absolute bottom-4 right-4 z-50 w-full md:w-96">
            <h3 className="text-xl font-extrabold text-gray-800">Manual Task Input</h3>
            {error && <div className="p-3 text-sm bg-red-100 text-red-700 rounded-lg">{error}</div>}
            <div className="space-y-3">
                <input id="name" type="text" value={name} onChange={(e) => setName(e.target.value)} required className="mt-1 block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 p-2 text-sm border" placeholder="Task Name"/>
                <input id="description" type="text" value={description} onChange={(e) => setDescription(e.target.value)} className="mt-1 block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 p-2 text-sm border" placeholder="Description"/>
                <input id="project" type="text" value={project} onChange={(e) => setProject(e.target.value)} required className="mt-1 block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 p-2 text-sm border" placeholder="Project Name"/>
                <div className="grid grid-cols-2 gap-3">
                    <input id="timeSlot" type="text" value={timeSlot} onChange={(e) => setTimeSlot(e.target.value)} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 p-1 text-sm border" placeholder="HH:MM AM - HH:MM PM"/>
                    <input id="budget" type="number" step="0.01" min="0" value={cashBudget} onChange={(e) => setCashBudget(Number(e.target.value))} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 p-1 text-sm border" placeholder="Budget"/>
                </div>
                <select value={taskPriority} onChange={(e) => setTaskPriority(e.target.value as any)} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 p-1 text-sm border">
                    <option value="High">High Priority</option>
                    <option value="Medium">Medium Priority</option>
                    <option value="Low">Low Priority</option>
                </select>
            </div>
            <button type="submit" disabled={isSubmitting || !name} className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg shadow-md text-sm font-medium hover:bg-blue-700 transition-colors">Add Daily Task</button>
        </form>
    );
};

// --- MAIN COMPONENT ---

const DUMMY_DAILY_TASKS: DailyTask[] = [
    { id: 'd-1', name: 'Morning Prep: Pack Lunches', description: 'Ensure all lunches are packed.', project: 'Meal & Food Prep', planningHorizon: 'Daily Focus', timeSlot: '07:00 AM - 07:30 AM', cashBudget: 50.00, taskPriority: 'High', status: 'pending', date: format(new Date(), 'yyyy-MM-dd') },
    { id: 'd-2', name: 'CashFlow Check: Pay Water Bill', description: 'Bill is due today.', project: 'Financial Management', planningHorizon: 'Daily Focus', timeSlot: '08:30 AM - 09:00 AM', cashBudget: 75.50, taskPriority: 'High', status: 'started', date: format(new Date(), 'yyyy-MM-dd') },
    { id: 'd-3', name: 'Quick Tidy: Mail and Bills', description: 'Sort through incoming mail.', project: 'Paperwork', planningHorizon: 'Daily Focus', timeSlot: '09:00 AM - 09:30 AM', cashBudget: 0.00, taskPriority: 'Medium', status: 'completed', date: format(new Date(), 'yyyy-MM-dd') },
    { id: 'd-4', name: 'Deep Clean: Vacuum Main Floor', description: 'Focus on living room/kitchen.', project: 'Weekly Chores', planningHorizon: 'Daily Focus', timeSlot: '11:00 AM - 12:00 PM', cashBudget: 0.00, taskPriority: 'Medium', status: 'pending', date: format(new Date(), 'yyyy-MM-dd') },
    { id: 'd-5', name: 'TaskFlow: Review Goals', description: 'Allocate 30 mins to review.', project: 'Planning & Strategy', planningHorizon: 'Daily Focus', timeSlot: '02:00 PM - 02:30 PM', cashBudget: 0.00, taskPriority: 'Low', status: 'pending', date: format(new Date(), 'yyyy-MM-dd') },
    { id: 'd-6', name: 'Meal Prep: Chop Veggies', description: 'Time-saver for evening.', project: 'Meal & Food Prep', planningHorizon: 'Daily Focus', timeSlot: '05:00 PM - 05:30 PM', cashBudget: 20.00, taskPriority: 'Medium', status: 'pending', date: format(new Date(), 'yyyy-MM-dd') },
    { id: 'd-7', name: 'Evening Routine: Tidy Kitchen', description: 'Wipe counters/load dishwasher.', project: 'Daily Maintenance', planningHorizon: 'Daily Focus', timeSlot: '08:00 PM - 08:30 PM', cashBudget: 0.00, taskPriority: 'Medium', status: 'pending', date: format(new Date(), 'yyyy-MM-dd') },
];

export function DailyView() {
  const [tasks, setTasks] = useState<DailyTask[]>(DUMMY_DAILY_TASKS);
  const [showForm, setShowForm] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());

  const addTask = (newTask: DailyTask) => {
      setTasks(prev => [...prev, newTask]);
      setShowForm(false);
  };

  const deleteTask = (taskId: string) => {
      setTasks(prev => prev.filter(t => t.id !== taskId));
  };

  const updateTaskStatus = (taskId: string, newStatus: DailyTask['status']) => {
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: newStatus } : t));
  };

  // Filter tasks for current date
  const filteredTasks = tasks.filter(t => t.date === format(currentDate, 'yyyy-MM-dd'));
  const scores = calculateScores(filteredTasks);

  return (
    <div id="daily" className="w-full flex-shrink-0 h-full p-8 snap-start overflow-y-auto bg-slate-50">
      <div className="w-full h-full flex flex-col">
        <div className="mb-6 flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-bold text-slate-800 mb-2 font-sans">Daily Focus</h1>
            <p className="text-xl text-slate-500">The Coach — Action: Time-Block Execution</p>
          </div>
          <div className="flex items-center gap-4">
              <DateSwitcher currentDate={currentDate} onDateChange={setCurrentDate} />
              <button 
                onClick={() => setShowForm(!showForm)}
                className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 transition-all shadow-md"
              >
                <Plus size={18} />
                Add Task
              </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 flex gap-6 overflow-hidden">
            {/* Left Pane: Summary & Reflection (Fixed Width) */}
            <div className="w-96 flex flex-col flex-shrink-0">
                <DailySummaryView tasks={filteredTasks} scores={scores} currentDate={currentDate} />
            </div>

            {/* Right Pane: Daily Calendar (Flex Grow) */}
            <div className="flex-1 flex flex-col min-w-0 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-4 border-b border-slate-100 bg-slate-50/30 flex items-center gap-2">
                    <CalendarIcon size={18} className="text-pink-500" />
                    <span className="font-bold text-slate-700">Daily Timeline</span>
                </div>
                <div className="flex-1 relative overflow-hidden bg-slate-50/30 p-4">
                    <DailyCalendarView tasks={filteredTasks} deleteTask={deleteTask} updateTaskStatus={updateTaskStatus} />
                </div>
            </div>

            <TaskForm onAddTask={addTask} isVisible={showForm} currentDate={currentDate} />
        </div>
      </div>
    </div>
  );
}
