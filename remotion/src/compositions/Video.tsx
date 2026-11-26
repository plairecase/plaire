import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {ClipLayer} from '../components/ClipLayer';
import {EndFrame} from '../components/EndFrame';
import {Hook} from '../components/Hook';
import {NativeText} from '../components/NativeText';
import type {VideoProps} from '../types';

/** Общий рендер для шаблонов p_* и n_*: план монтажа приходит готовым из planner/. */
export const Video: React.FC<VideoProps> = (p) => (
  <AbsoluteFill style={{backgroundColor: '#000'}}>
    <ClipLayer clips={p.clips} />
    {p.style === 'premium' ? <Hook screens={p.screens} color={p.textColor} /> : <NativeText screens={p.screens} />}
    {p.endFrame ? (
      <Sequence from={p.endFrame.from} durationInFrames={p.endFrame.durationInFrames} layout="none">
        <EndFrame spec={p.endFrame} />
      </Sequence>
    ) : null}
  </AbsoluteFill>
);
