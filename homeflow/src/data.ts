import type { LifeDomain, Project } from './types';

export const INITIAL_DOMAINS: LifeDomain[] = [
  { id: '1', name: 'Health', budgetScore: 6, timeScore: 4, scopeScore: 8, targetScore: 9, definitionOfSuccess: 'Vibrant energy, fit body, mental clarity.', color: '#ec4899' },
  { id: '2', name: 'Wealth', budgetScore: 8, timeScore: 7, scopeScore: 5, targetScore: 8, definitionOfSuccess: 'Financial freedom, abundant resources.', color: '#10b981' },
  { id: '3', name: 'Relationships', budgetScore: 5, timeScore: 3, scopeScore: 7, targetScore: 10, definitionOfSuccess: 'Deep connections, loving family, loyal friends.', color: '#f43f5e' },
  { id: '4', name: 'Growth', budgetScore: 4, timeScore: 6, scopeScore: 9, targetScore: 9, definitionOfSuccess: 'Continuous learning, skill mastery.', color: '#8b5cf6' },
  { id: '5', name: 'Career', budgetScore: 7, timeScore: 5, scopeScore: 6, targetScore: 9, definitionOfSuccess: 'Impactful work, recognition, leadership.', color: '#3b82f6' },
  { id: '6', name: 'Spirituality', budgetScore: 3, timeScore: 8, scopeScore: 4, targetScore: 8, definitionOfSuccess: 'Inner peace, purpose, connection to source.', color: '#f59e0b' },
];

export const INITIAL_PROJECTS: Project[] = [
  { id: '1', title: 'Marathon Training', domainId: '1', description: 'Run a sub-4 hour marathon', status: 'active', impact: 9, effort: 8, budget: 500 },
  { id: '2', title: 'Launch Side Hustle', domainId: '2', description: 'MVP for SaaS idea', status: 'active', impact: 10, effort: 9, budget: 1000 },
  { id: '3', title: 'Learn Spanish', domainId: '4', description: 'Conversational fluency', status: 'backlog', impact: 6, effort: 7, budget: 200 },
  { id: '4', title: 'Home Renovation', domainId: '2', description: 'Kitchen remodel', status: 'backlog', impact: 7, effort: 9, budget: 15000 },
  { id: '5', title: 'Meditation Habit', domainId: '6', description: 'Daily 20 mins', status: 'active', impact: 4, effort: 2, budget: 0 },
  { id: '6', title: 'Read 12 Books', domainId: '4', description: '1 book per month', status: 'active', impact: 7, effort: 4, budget: 300 },
];

export const TOTAL_CAPACITIES = {
  budget: 3000,
  scope: 50,
  time: 50
};
