/** Abstract product visual: documents transforming into structured fields & tables. */
export default function ProductHeroVisual() {
  return (
    <div
      aria-hidden
      className="product-hero-visual relative mx-auto w-full overflow-hidden"
    >
      <svg
        viewBox="0 0 520 320"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="h-auto w-full object-contain drop-shadow-2xl"
      >
        <defs>
          <linearGradient id="docGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#e8f4f4" stopOpacity="0.9" />
          </linearGradient>
          <linearGradient id="panelGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.98" />
            <stop offset="100%" stopColor="#f0faf9" stopOpacity="0.95" />
          </linearGradient>
          <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background glow */}
        <ellipse
          cx="260"
          cy="160"
          rx="200"
          ry="120"
          fill="#7dd3c0"
          fillOpacity="0.12"
          filter="url(#softGlow)"
        />

        {/* Source document stack */}
        <g transform="translate(24, 48)">
          <rect
            x="8"
            y="12"
            width="128"
            height="168"
            rx="8"
            fill="white"
            fillOpacity="0.15"
            stroke="white"
            strokeOpacity="0.2"
          />
          <rect
            x="0"
            y="0"
            width="128"
            height="168"
            rx="8"
            fill="url(#docGrad)"
            stroke="white"
            strokeOpacity="0.35"
            strokeWidth="1.5"
          />
          <rect x="16" y="20" width="72" height="6" rx="3" fill="#0d7377" fillOpacity="0.35" />
          <rect x="16" y="36" width="96" height="4" rx="2" fill="#64748b" fillOpacity="0.25" />
          <rect x="16" y="48" width="88" height="4" rx="2" fill="#64748b" fillOpacity="0.2" />
          <rect x="16" y="60" width="92" height="4" rx="2" fill="#64748b" fillOpacity="0.2" />
          <rect x="16" y="80" width="96" height="48" rx="4" fill="#0d7377" fillOpacity="0.06" stroke="#0d7377" strokeOpacity="0.15" />
          <line x1="24" y1="96" x2="104" y2="96" stroke="#0d7377" strokeOpacity="0.2" />
          <line x1="24" y1="108" x2="104" y2="108" stroke="#0d7377" strokeOpacity="0.15" />
          <line x1="24" y1="120" x2="88" y2="120" stroke="#0d7377" strokeOpacity="0.15" />
          <text x="16" y="148" fill="#0d7377" fillOpacity="0.5" fontSize="9" fontFamily="system-ui">
            Contract.pdf
          </text>
        </g>

        {/* Transform arrow / pipeline */}
        <g transform="translate(200, 130)">
          <circle cx="0" cy="0" r="28" fill="white" fillOpacity="0.12" stroke="white" strokeOpacity="0.3" />
          <path
            d="M-18 0 L18 0 M10 -8 L18 0 L10 8"
            stroke="#a7f3d0"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="-32" cy="0" r="4" fill="#6ee7b7" fillOpacity="0.8" />
          <circle cx="32" cy="0" r="4" fill="#6ee7b7" fillOpacity="0.8" />
        </g>

        {/* Structured output panel */}
        <g transform="translate(268, 36)">
          <rect
            width="228"
            height="248"
            rx="12"
            fill="url(#panelGrad)"
            stroke="white"
            strokeOpacity="0.4"
            strokeWidth="1.5"
          />
          <rect x="16" y="16" width="80" height="8" rx="4" fill="#0d7377" fillOpacity="0.7" />
          <rect x="16" y="32" width="120" height="5" rx="2.5" fill="#64748b" fillOpacity="0.3" />

          {/* Field chips */}
          <rect x="16" y="52" width="88" height="28" rx="6" fill="#ecfdf5" stroke="#10b981" strokeOpacity="0.35" />
          <text x="24" y="64" fill="#065f46" fontSize="7" fontWeight="600" fontFamily="system-ui">
            CONTRACT NO.
          </text>
          <text x="24" y="74" fill="#047857" fontSize="8" fontFamily="ui-monospace, monospace">
            W912HQ-24-C-0001
          </text>

          <rect x="112" y="52" width="72" height="28" rx="6" fill="#ecfdf5" stroke="#10b981" strokeOpacity="0.35" />
          <text x="120" y="64" fill="#065f46" fontSize="7" fontWeight="600" fontFamily="system-ui">
            NAICS
          </text>
          <text x="120" y="74" fill="#047857" fontSize="8" fontFamily="ui-monospace, monospace">
            541512
          </text>

          <rect x="16" y="88" width="96" height="28" rx="6" fill="#ecfdf5" stroke="#10b981" strokeOpacity="0.35" />
          <text x="24" y="100" fill="#065f46" fontSize="7" fontWeight="600" fontFamily="system-ui">
            EFFECTIVE DATE
          </text>
          <text x="24" y="110" fill="#047857" fontSize="8" fontFamily="ui-monospace, monospace">
            2024-10-01
          </text>

          {/* Table */}
          <rect x="16" y="128" width="196" height="96" rx="6" fill="white" stroke="#cbd5e1" strokeOpacity="0.6" />
          <rect x="16" y="128" width="196" height="22" rx="6" fill="#0d7377" fillOpacity="0.08" />
          <text x="24" y="142" fill="#0d7377" fontSize="7" fontWeight="600" fontFamily="system-ui">
            CLINs · Source verified
          </text>
          <line x1="24" y1="158" x2="204" y2="158" stroke="#e2e8f0" />
          <line x1="24" y1="174" x2="204" y2="174" stroke="#f1f5f9" />
          <line x1="24" y1="190" x2="204" y2="190" stroke="#f1f5f9" />
          <line x1="24" y1="206" x2="204" y2="206" stroke="#f1f5f9" />
          <text x="24" y="170" fill="#334155" fontSize="7" fontFamily="ui-monospace, monospace">
            0001 · Supplies
          </text>
          <text x="24" y="186" fill="#334155" fontSize="7" fontFamily="ui-monospace, monospace">
            0002 · Services
          </text>
          <text x="24" y="202" fill="#334155" fontSize="7" fontFamily="ui-monospace, monospace">
            0003 · ODC
          </text>

          {/* Verified badge */}
          <circle cx="196" cy="236" r="14" fill="#10b981" fillOpacity="0.15" />
          <path
            d="M190 236 L194 240 L202 232"
            stroke="#10b981"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>

        {/* Floating accent dots */}
        <circle cx="180" cy="60" r="3" fill="#6ee7b7" fillOpacity="0.6" />
        <circle cx="248" cy="280" r="2.5" fill="#a7f3d0" fillOpacity="0.5" />
        <circle cx="480" cy="80" r="2" fill="white" fillOpacity="0.4" />
      </svg>
    </div>
  );
}
