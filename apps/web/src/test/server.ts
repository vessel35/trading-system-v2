import { setupServer } from "msw/node";

import { emptyEvidenceHandlers } from "./fixtures/evidence";

export const server = setupServer(...emptyEvidenceHandlers);
