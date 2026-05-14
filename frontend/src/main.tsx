import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

// Docs: https://react.dev/reference/react-dom/client/createRoot

const el = document.getElementById("root");
if (!el) {
  throw new Error("Root element missing");
}
createRoot(el).render(<App />);
