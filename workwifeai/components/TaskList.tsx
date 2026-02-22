interface TaskListProps {
    tasks: string[];
  }
  
export default function TaskList({ tasks }: TaskListProps): JSX.Element {
return (
    <ul>
    {tasks.map((task, index) => (
        <li key={index}>{task}</li>
    ))}
    </ul>
);
}