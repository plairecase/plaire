import React from 'react';
import {AbsoluteFill, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import type {ClipSpec} from '../types';

const Clip: React.FC<{clip: ClipSpec}> = ({clip}) => {
  const frame = useCurrentFrame();
  const [s0, s1] = clip.pushIn ?? [1, 1];
  const scale = interpolate(frame, [0, clip.durationInFrames], [s0, s1], {extrapolateRight: 'clamp'});
  const d = clip.dissolveInFrames ?? 0;
  const opacity = d ? interpolate(frame, [0, d], [0, 1], {extrapolateRight: 'clamp'}) : 1;
  const blur = d ? interpolate(frame, [0, d], [6, 0], {extrapolateRight: 'clamp'}) : 0;
  return (
    <AbsoluteFill style={{opacity, filter: blur ? `blur(${blur}px)` : undefined}}>
      <OffthreadVideo
        src={staticFile(clip.src)}
        muted
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}}
      />
    </AbsoluteFill>
  );
};

export const ClipLayer: React.FC<{clips: ClipSpec[]}> = ({clips}) => (
  <AbsoluteFill style={{backgroundColor: '#000'}}>
    {clips.map((c, i) => (
      <Sequence key={i} from={c.from} durationInFrames={c.durationInFrames} layout="none">
        <Clip clip={c} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
