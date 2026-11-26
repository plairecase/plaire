import {Easing, interpolate} from 'remotion';
import {motion} from '../brand';

const [a, b, c, d] = motion.ease_in;
const [e, f, g, h] = motion.ease_out;
export const easeIn = Easing.bezier(a, b, c, d);   // быстрый старт, долгое мягкое торможение
export const easeOut = Easing.bezier(e, f, g, h);

export const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

/** 0→1 за durMs начиная с кадра start (кривая появления бренда). */
export const appear = (frame: number, start: number, durMs: number, fps: number) =>
  interpolate(frame, [start, start + msToFrames(durMs, fps)], [0, 1], {
    easing: easeIn,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

/** 1→0 в последние durMs отрезка длиной total. */
export const disappear = (frame: number, total: number, durMs: number, fps: number) =>
  interpolate(frame, [total - msToFrames(durMs, fps), total], [1, 0], {
    easing: easeOut,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
