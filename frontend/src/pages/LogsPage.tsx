import { useParams } from "react-router";

export function LogsPage() {
  const { name = "" } = useParams();
  return <h1 className="text-xl font-semibold">Logs: {name}</h1>;
}
