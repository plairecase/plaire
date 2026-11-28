import React, {useEffect, useMemo, useState} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {useThree} from '@react-three/fiber';
import {continueRender, delayRender, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {palette} from '../brand';

export type Scene3D = 'hero' | 'fly' | 'view';
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
  tune?: MaterialTune}> = ({obj, scene, total, frame, view, tune}) => {
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

export const Case3D: React.FC<{src: string; scene: Scene3D; total: number; view?: View; tune?: MaterialTune}> = (
  {src, scene, total, view, tune}) => {
  const {width, height} = useVideoConfig();
  const frame = useCurrentFrame();
  const obj = useModel(src);
  return (
    <div style={{position: 'absolute', inset: 0, background: scene === 'fly' ? 'transparent' : palette.paper}}>
      <ThreeCanvas width={width} height={height} shadows camera={{fov: 30, position: [0, 0, 4]}}
        gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[-2.5, 3, 3]} intensity={2.2} castShadow
          shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
        <directionalLight position={[3, 1, 2]} intensity={0.6} />
        {scene !== 'fly' ? (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]} receiveShadow>
            <planeGeometry args={[10, 10]} />
            <shadowMaterial opacity={0.18} />
          </mesh>
        ) : null}
        {obj ? <Model obj={obj} scene={scene} total={total} frame={frame} view={view} tune={tune} /> : null}
      </ThreeCanvas>
    </div>
  );
};
