import React from 'react';

// Вордмарк PLAIRE из дизайн-системы (векторная копия логотипа plaire.eu). Шрифтом не набирается.
export const Wordmark: React.FC<{width: number; color: string}> = ({width, color}) => (
  <svg viewBox="0 0 488.55 100" width={width} height={(width * 100) / 488.55}>
    <g fill={color}>
      <path d="M0,0 H16.6 V100 H0 Z" />
      <path d="M0,0 H40 A31.4,30.4 0 0 1 40,60.8 H0 Z M16.6,16.6 H40 A14.6,13.8 0 0 1 40,44.2 H16.6 Z" fillRule="evenodd" />
      <path d="M92.95,0 H109.55 V83.4 H155.95 V100 H92.95 Z" />
      <path d="M220.5,0 L265.7,100 H247.3 L241.11,86.3 H199.89 L193.7,100 H175.3 Z M220.5,40.71 L233.56,69.6 H207.44 Z" fillRule="evenodd" />
      <path d="M286.78,0 H303.38 V100 H286.78 Z" />
      <path d="M330.84,0 H347.44 V100 H330.84 Z" />
      <path d="M330.84,0 H370.84 A31.4,29.05 0 0 1 370.84,58.1 H330.84 Z M347.44,16.6 H370.84 A14.6,13.75 0 0 1 370.84,44.1 H347.44 Z" fillRule="evenodd" />
      <path d="M344.09,50 L365.69,50 L402.94,100 L381.34,100 Z" />
      <path d="M425.11,0 H488.51 V16.6 H441.71 V41.4 H476.61 V58 H441.71 V83.4 H488.51 V100 H425.11 Z" />
    </g>
  </svg>
);
