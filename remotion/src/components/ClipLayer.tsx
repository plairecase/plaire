import React from 'react';
import {AbsoluteFill, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import type {ClipSpec} from '../types';
import {easeIn} from './anim';

/** Энергичные переходы (правка владельца 27.11.2026):
 *  zoom  — входящий план из 125 % и размытия, резко садится на место;
 *  push  — входящий план выталкивает текущий снизу вверх;
 *  whip  — быстрый свайп вбок с размытием движения;
 *  punch — прямая склейка с коротким толчком масштаба 112 % → 100 % (в бит). */
const Clip: React.FC<{clip: ClipSpec}> = ({clip}) => {
  const frame = useCurrentFrame();
  const total = clip.durationInFrames;
  const [s0, s1] = clip.pushIn ?? [1, 1];
  let scale = interpolate(frame, [0, total], [s0, s1], {extrapolateRight: 'clamp'});
  let tx = 0;
  let ty = 0;
  let blur = 0;
  let opacity = 1;

  const tin = clip.transitionIn;
  if (tin && tin.type !== 'cut' && frame < tin.frames) {
    const p = interpolate(frame, [0, tin.frames], [0, 1], {easing: easeIn, extrapolateRight: 'clamp'});
    if (tin.type === 'zoom') {
      scale *= 1.25 - 0.25 * p;
      blur = 18 * (1 - p);
      opacity = Math.min(1, p * 2.5);
    } else if (tin.type === 'push') {
      ty = (1 - p) * 100;
      blur = 10 * (1 - p);
    } else if (tin.type === 'whip') {
      tx = (1 - p) * 100;
      blur = 30 * (1 - p);
    } else if (tin.type === 'punch') {
      scale *= 1.12 - 0.12 * p;
    }
  }
  if (tin && tin.type === 'impact') {
    // удар-наезд на первой доле (fix-02 §3.1): 1.00 → 1.12 за 2–3 кадра, затем мягко к 1.05
    const hit = tin.frames;
    scale =
      frame <= hit
        ? interpolate(frame, [0, hit], [1, 1.12], {extrapolateRight: 'clamp'})
        : interpolate(frame, [hit, total], [1.12, 1.05], {easing: easeIn, extrapolateRight: 'clamp'});
  }
  const tout = clip.transitionOut;
  if (tout && (tout.type === 'push' || tout.type === 'whip' || tout.type === 'zoom') && frame >= total - tout.frames) {
    const q = interpolate(frame, [total - tout.frames, total], [0, 1], {easing: easeIn, extrapolateLeft: 'clamp'});
    if (tout.type === 'push') {
      ty = -q * 100;
      blur = Math.max(blur, 10 * q);
    } else if (tout.type === 'whip') {
      tx = -q * 100;
      blur = Math.max(blur, 30 * q);
    } else {
      scale *= 1 + 0.12 * q;               // уходящий план чуть «влетает» в камеру
    }
  }
  return (
    <AbsoluteFill
      style={{
        opacity,
        filter: blur > 0.3 ? `blur(${blur}px)` : undefined,
        transform: `translate(${tx}%, ${ty}%) translateY(${clip.offsetY ?? 0}px)`,
      }}
    >
      <OffthreadVideo
        src={staticFile(clip.src)}
        muted
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}}
      />
    </AbsoluteFill>
  );
};

export const ClipLayer: React.FC<{clips: ClipSpec[]}> = ({clips}) => (
  <AbsoluteFill style={{backgroundColor: '#000', overflow: 'hidden'}}>
    {clips.map((c, i) => (
      <Sequence key={i} from={c.from} durationInFrames={c.durationInFrames} layout="none">
        <Clip clip={c} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
