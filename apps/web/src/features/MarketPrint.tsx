export function MarketPrint() {
  return (
    <svg
      className="market"
      viewBox="0 0 540 316"
      role="presentation"
      aria-hidden="true"
    >
      <defs>
        <pattern
          id="brick"
          width="16"
          height="10"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M0 0H16M8 0v5M0 5h16M0 5v5"
            stroke="#356d5f"
            strokeWidth=".7"
            fill="none"
          />
        </pattern>
        <pattern id="ridges" width="6" height="6" patternUnits="userSpaceOnUse">
          <path d="m0 6 6-6" stroke="#326454" strokeWidth=".7" />
        </pattern>
      </defs>
      <path d="M0 0h540v316H0z" fill="#d3e8d7" />
      <circle cx="405" cy="69" r="42" fill="#f4ca63" />
      <path
        d="M0 158v-25h42v-10h23v24h15v-43h35v45h18v-25h28v18h63v-29h47v32h84v-21h31v12h46v-25h38v18h38v-9h32v74H0z"
        fill="#a6c9b3"
      />
      <path
        d="M0 162q46-17 90-7t87 0q51-11 94 3t98-2q78-16 171-2v43H0z"
        fill="#8ab59e"
      />
      <g
        fill="#f5e7b5"
        stroke="#215346"
        strokeWidth="2.7"
        strokeLinejoin="round"
      >
        <path d="M0 201h89v78H0zM14 183h56v18H14zM73 173h79v106H73zM84 153h59v20H84z" />
        <path d="M152 275V141h32v-22h18v-13h94v13h19v22h33v134z" />
        <path d="M147 142h46v-8h112v8h49v9H147z" fill="#e4bb6b" />
        <path d="M208 106v-6q15-2 19-22 6 20 19 22v6m8 0v-6q15-2 19-22 6 20 19 22v6" />
        <path d="M154 141v-13q12-3 15-17 4 14 13 17v13m139 0v-13q10-3 14-17 4 14 13 17v13" />
        <path d="M192 275v-59q0-37 58-63 57 25 57 63v59" fill="#e3bd75" />
        <path d="M204 275v-58q0-27 46-49 45 22 45 49v58z" fill="#285c4e" />
        <path
          d="M213 275v-55q0-24 37-42 37 18 37 42v55z"
          fill="#b8d4be"
          stroke="none"
        />
        <path
          d="M218 257v-30l14-9 11 7 13-18 11 6 17-6v50z"
          stroke="none"
          fill="#739b83"
        />
        <path d="M156 163h27v95h-27zm162 0h26v95h-26z" fill="url(#brick)" />
        <path d="M347 186h91v91h-91zM353 170h81v16h-81zM437 161h103v116H437z" />
        <path d="M354 205h73l9 18h-89z" fill="#f4ca63" />
        <path d="M354 223h73v51h-73z" fill="url(#ridges)" />
        <path d="M451 184h70v18h-70zm0 32h70v58h-70z" fill="#78a68a" />
        <path d="M457 223h57m-57 8h57m-57 8h57m-57 8h57" />
        <path d="M4 212h64l6 15H0z" fill="#76a28b" />
        <path d="M9 227v47m46-47v47M91 190h43v49H91z" fill="#d7bd78" />
      </g>
      <path d="M0 276h540v40H0z" fill="#ddcfaa" />
      <path
        d="M0 276h540m-330 40 29-39m57 39-30-39"
        fill="none"
        stroke="#50715c"
        strokeWidth="2"
      />
      <g stroke="#234e41" strokeWidth="3" fill="none">
        <circle cx="90" cy="275" r="12" />
        <circle cx="131" cy="275" r="12" />
        <path d="m90 275 16-25 15 25H90l23-17h11l7 17m-26-27h-8m25 6-3-11h9" />
      </g>
      <g fill="#295b4c">
        <path d="M26 257h14l-3 17h-8z" />
        <path d="M33 258q-19-23-11-27 9 7 12 24-2-25 7-30 7 12-8 33" />
      </g>
      <g stroke="#285749" strokeWidth="2" fill="none">
        <path d="M70 58q6-5 11 0 4-5 10-3m19 13q4-4 8 0 4-4 8-2m312 22q5-6 11-1 4-6 11-4" />
      </g>
    </svg>
  );
}
