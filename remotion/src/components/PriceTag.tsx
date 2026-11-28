import React from 'react';
import {effects, FONT, palette, type} from '../brand';
import type {TextColor} from '../types';
import {colorOf, eyebrowStyle, shadowOf} from './Hook';

/** €29 | • PLAIRE.EU — контурная рамка 2 px с прямыми углами, без заливки. */
export const PriceTag: React.FC<{price: string; site: string; color: TextColor}> = ({price, site, color}) => {
  const c = colorOf(color);
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 24,
        padding: '14px 32px',
        border: `${effects.hairline_px}px solid ${c}`,
        borderRadius: 0,                  // прямые углы (fix-01/fix-03)
      }}
    >
      <span
        style={{
          fontFamily: FONT,
          fontWeight: type.price[0],
          fontSize: type.price[1],
          lineHeight: '52px',
          letterSpacing: '0.04em',
          color: c,
          textShadow: shadowOf(color),
        }}
      >
        {price}
      </span>
      <span style={{width: effects.hairline_px, height: 44, background: c}} />
      <span style={{display: 'inline-flex', alignItems: 'center', gap: 12}}>
        <span
          style={{
            width: effects.signal_dot_px,
            height: effects.signal_dot_px,
            borderRadius: '50%',
            background: palette.signal,
          }}
        />
        <span style={eyebrowStyle(color)}>{site}</span>
      </span>
    </div>
  );
};
