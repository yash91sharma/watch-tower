// MSW server for tests. setup.ts starts it, and resets it after each test.
import { setupServer } from "msw/node";

import { handlers } from "@/test/handlers";

export const server = setupServer(...handlers);
