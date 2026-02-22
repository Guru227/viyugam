export type DomainName = 'Health' | 'Wealth' | 'Relationships' | 'Growth' | 'Career' | 'Spirituality';

export interface LifeDomain {
  id: string;
  name: DomainName;
  // Scores for the "Lenses" (1-10)
  budgetScore: number; // Financial capacity
  timeScore: number;   // Time capacity
  scopeScore: number;  // Requirement clarity / Satisfaction
  
  targetScore: number; // General target (can be an average or specific metric)
  definitionOfSuccess: string;
  color: string;
}

export interface Project {
  id: string;
  title: string;
  domainId: string; // Renamed from aspectId
  description: string;
  status: 'backlog' | 'active' | 'completed' | 'paused';
  impact: number; // 1-10
  effort: number; // 1-10
  budget: number;
  deadline?: Date;
}

export interface Milestone {
  id: string;
  projectId: string;
  title: string;
  status: 'pending' | 'in-progress' | 'completed';
  dueDate?: Date;
  costEstimate: number;
  timeEstimateHours: number;
}

export interface Task {
  id: string;
  milestoneId: string;
  title: string;
  status: 'todo' | 'doing' | 'done';
  scheduledDate?: Date;
  startTime?: string; // HH:MM format (24h)
  duration?: number; // minutes
  deadline?: Date;
  project?: string;
  actualDuration?: number;
}
export interface DailyTask {
  id: string;
  name: string;
  description: string;
  project: string;
  planningHorizon: string;
  timeSlot: string | null;
  cashBudget: number;
  taskPriority: 'High' | 'Medium' | 'Low';
  status: 'pending' | 'started' | 'completed';
  date: string; // ISO Date string YYYY-MM-DD
  createdAt?: string;
}
