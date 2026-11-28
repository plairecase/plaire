import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {Case3D} from '../components/Case3D';
import {ClipLayer} from '../components/ClipLayer';
import {EndFrame} from '../components/EndFrame';
import {Hook} from '../components/Hook';
import {NativeText} from '../components/NativeText';
import type {VideoProps} from '../types';

/** Общий рендер для шаблонов p_* и n_*: план монтажа приходит готовым из planner/. */
export const Video: React.FC<VideoProps> = (p) => (
  <AbsoluteFill style={{backgroundColor: '#000'}}>
    <ClipLayer clips={p.clips} />
    {(p.threeD ?? []).map((l, i) => (
      <Sequence key={`3d${i}`} from={l.from} durationInFrames={l.durationInFrames} layout="none">
        <Case3D src={l.model} scene={l.type} total={l.durationInFrames} src2={l.model2} tune={l.tune}
          tune2={l.tune2} bg={l.bg} light={l.light} grain={l.grain} fade={l.fade} ink={l.ink} />
      </Sequence>
    ))}
    {p.style === 'premium' ? <Hook screens={p.screens} color={p.textColor} /> : <NativeText screens={p.screens} />}
    {p.endFrame ? (
      <Sequence from={p.endFrame.from} durationInFrames={p.endFrame.durationInFrames} layout="none">
        <EndFrame spec={p.endFrame} />
      </Sequence>
    ) : null}
  </AbsoluteFill>
);
