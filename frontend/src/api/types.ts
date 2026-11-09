// Named types for the API data, from the generated schema (pnpm gen:api).
import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export type ContainerOut = Schemas["ContainerOut"];
export type ContainerDetail = Schemas["ContainerDetail"];
export type Group = Schemas["GroupOut"];
export type Health = ContainerOut["health"];
export type SecretState = Schemas["SecretState"];
export type Settings = Schemas["Settings"];
export type SettingsOut = Schemas["SettingsOut"];
export type SetupBegin = Schemas["SetupBeginOut"];
export type Severity = Schemas["Severity"];
export type Status = Schemas["Status"];
export type Update = Schemas["UpdateOut"];
