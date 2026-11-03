import { useParams } from "react-router";

export function ContainerPage() {
  const { name = "" } = useParams();
  return <h1 className="text-xl font-semibold">{name}</h1>;
}
