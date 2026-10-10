export function SplashLogo() {
  return (
    <svg
      class="slogo"
      viewBox="0 0 512 512"
      role="img"
      aria-label="Travel Friends"
    >
      <defs>
        <linearGradient id="sbg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#1D2E86"/>
          <stop offset="1" stop-color="#0A0F2C"/>
        </linearGradient>
        <linearGradient id="sgl" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#5FD8FF"/>
          <stop offset="1" stop-color="#1E55E8"/>
        </linearGradient>
        <linearGradient id="sor" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#FF9A3D"/>
          <stop offset="1" stop-color="#F2547D"/>
        </linearGradient>
        <clipPath id="scp">
          <circle cx="248" cy="272" r="150"/>
        </clipPath>
      </defs>
      <rect width="512" height="512" rx="112" fill="url(#sbg)"/>
      <circle cx="248" cy="272" r="150" fill="url(#sgl)"/>
      <g clip-path="url(#scp)">
        <circle cx="190" cy="206" r="30" fill="#fff"/>
        <path
          d="M118 400C118 300 150 252 190 252S262 300 262 400Z"
          fill="#fff"
        />
        <circle cx="316" cy="198" r="30" fill="url(#sor)"/>
        <path
          d="M250 420C250 300 290 244 316 244S400 300 400 420Z"
          fill="url(#sor)"
          opacity=".96"
        />
      </g>
      <path
        d="M62 330C110 420 290 440 400 340 460 285 440 190 330 150"
        fill="none"
        stroke="#fff"
        stroke-width="13"
        stroke-linecap="round"
      />
      <g transform="translate(326 78) rotate(32 48 48) scale(4)">
        <path
          fill="#fff"
          d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"
        />
      </g>
    </svg>
  );
}
