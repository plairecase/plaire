import React from 'react';
import {Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {effects, FONT, palette, TEXT_LEFT, TEXT_RIGHT, type} from '../brand';
import type {TextScreen} from '../types';
import {appear, msToFrames} from './anim';

/** Нативный стиль: одна фраза, белый TikTok Sans 600 ~58 px с мягкой тенью, верхняя треть.
 *  Слова выскакивают по одному (правка владельца 27.11.2026). */
const Screen: React.FC<{s: TextScreen}> = ({s}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = s.text.split(' ');
  return (
    <div
      style={{
        position: 'absolute',
        left: TEXT_LEFT,
        width: TEXT_RIGHT - TEXT_LEFT,
        top: 330,
        textAlign: 'center',
        fontFamily: FONT,
        fontWeight: type.native[0],
        fontSize: type.native[1],
        lineHeight: '70px',
        color: palette.on_photo,
        textShadow: effects.text_on_photo_shadow,
        textWrap: 'balance',
      }}
    >
      {words.map((w, i) => {
        const p = appear(frame, msToFrames(80 * i, fps), 260, fps);
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              opacity: p,
              transform: `translateY(${(1 - p) * 18}px) scale(${0.85 + 0.15 * p})`,
              marginRight: '0.22em',
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};

export const NativeText: React.FC<{screens: TextScreen[]}> = ({screens}) => (
  <>
    {screens.map((s, i) => (
      <Sequence key={i} from={s.from} durationInFrames={s.durationInFrames} layout="none">
        <Screen s={s} />
      </Sequence>
    ))}
  </>
);
