import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT, TEXT_LEFT, type, W} from '../brand';
import type {EndFrameSpec} from '../types';
import {appear} from './anim';
import {colorOf, eyebrowStyle, shadowOf} from './Hook';
import {PriceTag} from './PriceTag';
import {Wordmark} from './Wordmark';

/** Финал поверх живого кадра: вордмарк сверху, ценник, строка доставки. Без чёрной карточки. */
export const EndFrame: React.FC<{spec: EndFrameSpec}> = ({spec}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const mark = appear(frame, 0, 900, fps);
  const tag = appear(frame, Math.round(0.3 * fps), 700, fps);
  const c = colorOf(spec.color);
  const wmW = 440;
  return (
    <>
      <div style={{position: 'absolute', top: 300, left: (W - wmW) / 2, opacity: mark}}>
        <Wordmark width={wmW} color={c} />
      </div>
      <div style={{position: 'absolute', top: 300 + 90 + 28, left: 0, width: W, textAlign: 'center', opacity: mark}}>
        <span style={eyebrowStyle(spec.color)}>{spec.eyebrow}</span>
      </div>
      <div style={{position: 'absolute', left: TEXT_LEFT, top: 1090, opacity: tag}}>
        <PriceTag price={spec.price} site={spec.site} color={spec.color} />
        <div
          style={{
            marginTop: 20,
            fontFamily: FONT,
            fontWeight: type.fine[0],
            fontSize: type.fine[1],
            lineHeight: '32px',
            color: c,
            textShadow: shadowOf(spec.color),
          }}
        >
          {spec.shipping}
        </div>
      </div>
    </>
  );
};
