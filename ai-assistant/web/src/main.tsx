import React from "react";
import ReactDOM from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "../../../circuit-designer/packages/react/src/styles.css";
import "../../../circuit-designer/packages/document-a2ui-react/src/styles.css";

import { App } from "./App";
import { AssistantAppProvider } from "./runtime";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AssistantAppProvider>
      <App />
    </AssistantAppProvider>
  </React.StrictMode>,
);
