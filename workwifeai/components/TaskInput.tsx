import { useState } from 'react';

interface TaskInputProps {
  onAddTask: (newTask: string) => void;
}

export default function TaskInput({ onAddTask }: TaskInputProps): JSX.Element {
  const [newTask, setNewTask] = useState('');

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    onAddTask(newTask);
    setNewTask('');
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={newTask}
        onChange={(e) => setNewTask(e.target.value)}
      />
      <button type="submit">Add Task</button>
    </form>
  );
}