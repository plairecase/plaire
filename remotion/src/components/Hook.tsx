import React from 'react';
import {Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {effects, FONT, motion, palette, TEXT_LEFT, TEXT_RIGHT, type} from '../brand';
import type {TextColor, TextScreen} from '../types';
import {appear, disappear, msToFrames} from './anim';

export const colorOf = (c: TextColor) => (c === 'ink' ? palette.ink : palette.on_photo);
export const shadowOf = (c: TextColor) => (c === 'white' ? effects.text_on_photo_shadow : 'none');

export const eyebrowStyle = (c: TextColor): React.CSSProperties => ({
  fontFamily: FONT,
  fontWeight: type.eyebrow[0],
  fontSize: type.eyebrow[1],
  lineHeight: '32px',
  letterSpacing: `${type.eyebrow_tracking_em}em`,
  fontStretch: `${type.eyebrow_stretch_pct}%`,
  textTransform: 'uppercase',
  color: colorOf(c),
  textShadow: shadowOf(c),
});

/** Премиум-хук: eyebrow + display Light 96, x 120, y ≈ 300. */
const HookScreen: React.FC<{s: TextScreen; color: TextColor}> = ({s, color}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const out = disappear(frame, s.durationInFrames, motion.text_out_ms, fps);
  const words = s.text.split(' ');
  const eyeIn = s.animateIn ? appear(frame, 0, motion.text_in_ms, fps) : 1;
  const wordsStart = s.animateIn && s.eyebrow ? msToFrames(200, fps) : 0;
  return (
    <div style={{position: 'absolute', left: TEXT_LEFT, top: 300, width: TEXT_RIGHT - TEXT_LEFT, opacity: out}}>
      {s.eyebrow ? (
        <div
          style={{
            ...eyebrowStyle(color),
            marginBottom: 24,
            opacity: eyeIn,
            transform: `translateY(${(1 - eyeIn) * motion.text_rise_px}px)`,
          }}
        >
          {s.eyebrow}
        </div>
      ) : null}
      <div
        style={{
          fontFamily: FONT,
          fontWeight: type.display[0],
          fontSize: type.display[1],
          lineHeight: '100px',
          letterSpacing: '-0.02em',
          color: colorOf(color),
          textShadow: shadowOf(color),
        }}
      >
        {words.map((w, i) => {
          const p = s.animateIn
            ? appear(frame, wordsStart + msToFrames(motion.stagger_word_ms * i, fps), motion.text_in_ms, fps)
            : 1;
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                opacity: p,
                transform: `translateY(${(1 - p) * motion.text_rise_px}px)`,
                marginRight: '0.24em',
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </div>
  );
};

export const Hook: React.FC<{screens: TextScreen[]; color: TextColor}> = ({screens, color}) => (
  <>
    {screens.map((s, i) => (
      <Sequence key={i} from={s.from} durationInFrames={s.durationInFrames} layout="none">
        <HookScreen s={s} color={color} />
      </Sequence>
    ))}
  </>
);
