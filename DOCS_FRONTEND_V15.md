# PROJECT ROODHA: FRONTEND MASTER DOC (v1.5.7)

## React Component Structure
The frontend is constructed using a modern **React (Vite)** architecture, utilizing functional components and hooks for state management. It is designed around modular units, including specific atomic components in the `src/components/ui/` directory and larger domain-specific views like `MachineLoadRadar` and `AuditTrailPanel`. This modularity supports the rapid evolution outlined in the Stage 2 and Stage 3 Roadmap goals.

## JetBrains Mono for Shop-Floor Clarity
Adhering to the v1.5 "Industrial Hardening" UI/UX specifications, **JetBrains Mono** is mandated globally for all numeric data. This design choice guarantees maximum legibility of critical metrics (e.g., job quantities, due dates, machine load metrics) in high-glare, rugged factory environments.

## "Delay Guard" Color Rendering
The frontend consumes the `alert_priority` calculated by the backend to implement the "Delay Guard" visual feedback system. By leveraging conditional Tailwind CSS utility classes, the UI renders immediate, high-visibility cues:
- **CRITICAL/Overdue**: Renders intense pulsing "Safety Orange" and Reds.
- **HIGH/<24h**: Renders warnings (Yellow/Amber) to alert supervisors.
- **NORMAL**: Remains standard brand colors or neutral tones.
This ensures that operators and managers can assess shop-floor health at a glance without reading detailed tables.
