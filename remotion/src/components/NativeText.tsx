import React from 'react';
import {Sequence} from 'remotion';
import {effects, FONT, palette, TEXT_LEFT, TEXT_RIGHT, type} from '../brand';
import type {TextScreen} from '../types';

/** Нативный стиль: одна фраза, белый TikTok Sans 600 ~58 px с мягкой тенью, верхняя треть. */
export const NativeText: React.FC<{screens: TextScreen[]}> = ({screens}) => (
  <>
    {screens.map((s, i) => (
      <Sequence key={i} from={s.from} durationInFrames={s.durationInFrames} layout="none">
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
          {s.text}
        </div>
      </Sequence>
    ))}
  </>
);
