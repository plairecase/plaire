import React, {useEffect, useMemo, useState} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {useThree} from '@react-three/fiber';
import {continueRender, delayRender, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {palette} from '../brand';

export type Scene3D = 'hero' | 'fly' | 'view' | 'two_colours' | 'profile';
/** Свет как в соседнем реальном плане (раздел 4): откуда основной свет и тёплый ли он. */
export type Light3D = {x: number; y: number; warm: boolean};
export type View = 'top' | 'three_quarter' | 'edge' | 'back';

/** Модель .glb: нормируем по наибольшей стороне, центрируем, Y вверх (раздел 8 инструкции). */
export type MaterialTune = {roughness?: number | null; tint?: number; normalScale?: number | null};

const tuneMaterials = (obj: THREE.Object3D, tune?: MaterialTune) => {
  if (!tune) return;
  obj.traverse((o) => {
    const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if (!m || !(m as THREE.MeshStandardMaterial).isMeshStandardMaterial) return;
    const name = (m.name || '').toLowerCase();
    if (name.includes('metal') || name.includes('magnet') || m.metalness > 0.5) return;   // магниты не трогаем
    if (tune.roughness != null) m.roughness = tune.roughness;
    if (tune.tint != null && tune.tint !== 1) m.color.multiplyScalar(tune.tint);
    if (tune.normalScale != null && m.normalMap) m.normalScale.setScalar(tune.normalScale);
    m.needsUpdate = true;
  });
};

const useModel = (src: string) => {
  const [obj, setObj] = useState<THREE.Object3D | null>(null);
  const [handle] = useState(() => delayRender(`3D ${src}`));
  useEffect(() => {
    new GLTFLoader().load(
      staticFile(src),
      (g) => {
        const root = g.scene;
        const box = new THREE.Box3().setFromObject(root);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const s = 1 / Math.max(size.x, size.y, size.z);
        root.position.sub(center.multiplyScalar(1));
        const face = new THREE.Group();          // разворот: самая тонкая ось чехла → к камере (Z)
        face.add(root);
        const thin = Math.min(size.x, size.y, size.z);
        if (thin === size.y) face.rotation.x = Math.PI / 2;
        else if (thin === size.x) face.rotation.y = Math.PI / 2;
        const wrap = new THREE.Group();
        wrap.add(face);
        wrap.scale.setScalar(s);
        root.traverse((o) => {
          if ((o as THREE.Mesh).isMesh) {
            (o as THREE.Mesh).castShadow = true;
          }
        });
        setObj(wrap);
        continueRender(handle);
      },
      undefined,
      (e) => {
        throw new Error('Не загрузилась 3D-модель ' + src + ': ' + e);
      },
    );
  }, [src, handle]);
  return obj;
};

/** Сцена рисуется только при смене кадра; модель, загруженная позже, иначе не попадёт в кадр
 *  (особенно в стоп-кадре). Принудительно перерисовываем и только потом отпускаем рендер. */
const DrawNow: React.FC = () => {
  const advance = useThree((st) => st.advance);
  const [handle] = useState(() => delayRender('3D: первая отрисовка модели'));
  useEffect(() => {
    advance(performance.now());
    const id = requestAnimationFrame(() => {
      advance(performance.now());
      continueRender(handle);
    });
    return () => cancelAnimationFrame(id);
  }, [advance, handle]);
  return null;
};

const Model: React.FC<{obj: THREE.Object3D; scene: Scene3D; total: number; frame: number; view?: View;
  tune?: MaterialTune; slot?: number}> = ({obj, scene, total, frame, view, tune, slot = 0}) => {
  const clone = useMemo(() => {
    const c = obj.clone(true);
    c.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh && mesh.material) mesh.material = (mesh.material as THREE.Material).clone();
    });
    tuneMaterials(c, tune);
    return c;
  }, [obj, tune]);
  if (!clone) return null;
  const ease = Easing.bezier(0.16, 1, 0.3, 1);
  let rotY = 0, rotX = 0.35, scale = 1, y = 0, z = 0;
  if (scene === 'view') {
    // контрольный лист: фиксированные ракурсы
    const deg = Math.PI / 180;
    const V: Record<View, [number, number]> = {top: [0, 0], three_quarter: [18 * deg, -38 * deg],
      edge: [8 * deg, 88 * deg], back: [0, 180 * deg]};
    [rotX, rotY] = V[view ?? 'top'];
    scale = 0.85;
  } else if (scene === 'hero') {
    // финал: медленный поворот 0 → 200°, лёгкое парение; чехол ниже текста
    const p = interpolate(frame, [0, total], [0, 1], {easing: ease, extrapolateRight: 'clamp'});
    rotY = -0.6 + p * (200 * Math.PI) / 180;
    y = -0.26 + 0.015 * Math.sin(frame / 12);       // центр чехла ≈ 62 % высоты кадра, под ценой
    scale = 0.64;
  } else if (scene === 'two_colours') {
    // s_two_colours: оба чехла рядом, синхронный поворот на 30°, лёгкий параллакс (передний чуть быстрее)
    const p = interpolate(frame, [0, total], [0, 1], {easing: ease, extrapolateRight: 'clamp'});
    const side = slot === 0 ? -1 : 1;
    rotX = 0.12;
    rotY = (-15 + 30 * p) * (Math.PI / 180) - side * 0.12;
    scale = 0.5;
    z = slot === 0 ? 0.06 : -0.06;
    const drift = (slot === 0 ? 0.03 : 0.015) * (p - 0.5);
    return (
      <group position={[side * 0.29 + drift, 0.02, z]} rotation={[rotX, rotY, 0]} scale={scale}>
        <DrawNow />
        <primitive object={clone} />
      </group>
    );
  } else if (scene === 'profile') {
    // s_profile: из 3/4 поворачивается на ребро и останавливается в профиль (последняя треть — стоп)
    const p = interpolate(frame, [0, total * 0.62], [0, 1], {easing: ease, extrapolateRight: 'clamp'});
    rotX = 0.1 - 0.1 * p;
    rotY = (-35 + 125 * p) * (Math.PI / 180);
    scale = 0.78;
    y = 0.0;
  } else {
    // переход: чехол влетает, вращаясь, закрывает кадр в середине (там склейка) и пролетает сквозь камеру
    const p = frame / Math.max(1, total);
    rotY = p * Math.PI * 2.2;
    rotX = 0.5 - p * 0.6;
    // полностью закрывает кадр лишь 2–3 кадра (иначе читается как «пустая вставка»)
    scale = interpolate(p, [0, 0.62, 0.8, 1], [0.25, 2.4, 6, 14], {easing: Easing.in(Easing.quad)});
    z = 0;
  }
  return (
    <group position={[0, y, z]} rotation={[rotX, rotY, 0]} scale={scale}>
      <DrawNow />
      <primitive object={clone} />
    </group>
  );
};

/** Плёночное зерно под уровень исходников: 3D не должна быть чище и резче реальных кадров (раздел 4). */
const Grain: React.FC<{amount: number; seed: number}> = ({amount, seed}) =>
  amount > 0 ? (
    <svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: amount, mixBlendMode: 'overlay'}}>
      <filter id={`g${seed}`}>
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={seed} stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter={`url(#g${seed})`} />
    </svg>
  ) : null;

/** Выноска к торцу (s_profile): точка на ребре и тонкая линия вправо, появляется после остановки. */
const Callout: React.FC<{frame: number; total: number; color: string}> = ({frame, total, color}) => {
  const p = interpolate(frame, [total * 0.62, total * 0.82], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1)});
  if (p <= 0) return null;
  const x0 = 600, y0 = 960, len = 300 * p;
  return (
    <svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
      <circle cx={x0} cy={y0} r={7 * Math.min(1, p * 3)} fill={color} />
      <line x1={x0} y1={y0} x2={x0 + len} y2={y0} stroke={color} strokeWidth={3} />
    </svg>
  );
};

export const Case3D: React.FC<{src: string; scene: Scene3D; total: number; view?: View; tune?: MaterialTune;
  src2?: string; tune2?: MaterialTune; bg?: string; light?: Light3D; grain?: number; fade?: number; ink?: string}> = (
  {src, scene, total, view, tune, src2, tune2, bg, light, grain = 0, fade = 0, ink}) => {
  const {width, height} = useVideoConfig();
  const frame = useCurrentFrame();
  const obj = useModel(src);
  const obj2 = useModel(src2 ?? src);
  const L = light ?? {x: -1, y: 1, warm: false};
  const key = L.warm ? '#fff1de' : '#ffffff';
  const segment = scene === 'two_colours' || scene === 'profile';
  const back = scene === 'fly' ? 'transparent' : (bg ?? palette.paper);
  // 3 кадра кросс-фейда реальный → 3D и 3D → реальный (раздел 2, механика п. 4)
  const opacity = fade > 0 ? Math.min(interpolate(frame, [0, fade], [0, 1], {extrapolateRight: 'clamp'}),
    interpolate(frame, [total - fade, total], [1, 0], {extrapolateLeft: 'clamp'})) : 1;
  const floor = segment ? (scene === 'profile' ? -0.42 : -0.3) : -0.5;
  return (
    <div style={{position: 'absolute', inset: 0, background: back, opacity}}>
      {segment ? <div style={{position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.16) 100%)'}} /> : null}
      <div style={{position: 'absolute', inset: 0, filter: segment ? 'blur(0.5px)' : undefined}}>
        <ThreeCanvas width={width} height={height} shadows camera={{fov: 30, position: [0, 0, 4]}}
          gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}}>
          <ambientLight intensity={0.55} />
          <directionalLight position={[2.8 * L.x, 3 * Math.max(0.4, L.y), 3]} intensity={2.2} color={key} castShadow
            shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
          <directionalLight position={[-2.6 * L.x, 1, 2]} intensity={0.6} />
          {scene !== 'fly' ? (
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, floor, 0]} receiveShadow>
              <planeGeometry args={[10, 10]} />
              <shadowMaterial opacity={0.2} />
            </mesh>
          ) : null}
          {obj ? <Model obj={obj} scene={scene} total={total} frame={frame} view={view} tune={tune} slot={0} /> : null}
          {scene === 'two_colours' && obj2 ? (
            <Model obj={obj2} scene={scene} total={total} frame={frame} tune={tune2} slot={1} />
          ) : null}
        </ThreeCanvas>
      </div>
      {segment ? <Grain amount={grain} seed={frame % 97} /> : null}
      {scene === 'profile' ? <Callout frame={frame} total={total} color={ink ?? palette.ink} /> : null}
    </div>
  );
};
